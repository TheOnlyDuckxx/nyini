from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import json
from pathlib import Path
import threading
import time
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from src.domain.models import WallhavenSearchPage, WallhavenSearchRequest, WallhavenSearchResult, WallhavenStatus
from src.i18n import tr


def _normalize_blacklist_tokens(value: str) -> list[str]:
    return [token.strip() for token in value.replace(",", " ").split() if token.strip()]


def _apply_blacklist(query: str, blacklist: str) -> str:
    query = query.strip()
    blacklist_tokens = _normalize_blacklist_tokens(blacklist)
    if not blacklist_tokens:
        return query
    blacklist_query = " ".join(f"-{token.lstrip('-')}" for token in blacklist_tokens)
    return f"{query} {blacklist_query}".strip()


class RateLimiter:
    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        while True:
            wait_time = 0.0
            with self._lock:
                now = time.monotonic()
                while self._timestamps and now - self._timestamps[0] >= self.window_seconds:
                    self._timestamps.popleft()
                if len(self._timestamps) < self.limit:
                    self._timestamps.append(now)
                    return
                wait_time = max(0.01, self.window_seconds - (now - self._timestamps[0]))
            time.sleep(wait_time)


@dataclass(slots=True)
class WallhavenClient:
    cache_root: Path
    api_base: str = "https://wallhaven.cc/api/v1"
    user_agent: str = "Nyini/0.1"
    rate_limit_per_minute: int = 45
    _rate_limiter: RateLimiter = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.thumbs_root.mkdir(parents=True, exist_ok=True)
        self._rate_limiter = RateLimiter(self.rate_limit_per_minute, 60)

    @property
    def thumbs_root(self) -> Path:
        return self.cache_root / "thumbs"

    def status(self, api_key: str = "") -> WallhavenStatus:
        has_key = bool(api_key.strip())
        if has_key:
            return WallhavenStatus(
                available=True,
                api_key_configured=True,
                message=tr("Wallhaven disponible avec cle API configuree."),
                rate_limit_per_minute=self.rate_limit_per_minute,
            )
        return WallhavenStatus(
            available=True,
            api_key_configured=False,
            message=tr("Wallhaven disponible en mode SFW sans cle API."),
            rate_limit_per_minute=self.rate_limit_per_minute,
        )

    def search(self, request: WallhavenSearchRequest, *, api_key: str = "") -> WallhavenSearchPage:
        params: dict[str, str | int] = {
            "q": _apply_blacklist(request.query, request.blacklist),
            "page": max(1, request.page),
            "purity": request.purity or "100",
        }
        if request.ratios.strip():
            params["ratios"] = request.ratios.strip()
        if request.atleast.strip():
            params["atleast"] = request.atleast.strip()
        if api_key.strip():
            params["apikey"] = api_key.strip()
        payload = self._get_json(f"{self.api_base}/search?{urlencode(params)}")
        meta = payload.get("meta", {})
        results = tuple(self._parse_search_item(item) for item in payload.get("data", []))
        return WallhavenSearchPage(
            request=request,
            results=results,
            current_page=int(meta.get("current_page", request.page or 1) or 1),
            last_page=int(meta.get("last_page", request.page or 1) or 1),
            total=int(meta.get("total", len(results)) or len(results)),
        )

    def fetch_wallpaper(self, wallhaven_id: str, *, api_key: str = "") -> WallhavenSearchResult:
        query = f"?{urlencode({'apikey': api_key.strip()})}" if api_key.strip() else ""
        payload = self._get_json(f"{self.api_base}/w/{wallhaven_id}{query}")
        return self._parse_search_item(payload["data"])

    def cache_thumbnail(self, result: WallhavenSearchResult) -> Path:
        return self._download_file(result.preview_url, self._thumb_path_for(result))

    def download_image(self, result: WallhavenSearchResult, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(urlparse(result.image_url).path).suffix or self._suffix_from_type(result.file_type)
        destination = destination_dir / f"wallhaven-{result.wallhaven_id}{suffix}"
        return self._download_file(result.image_url, destination)

    def _thumb_path_for(self, result: WallhavenSearchResult) -> Path:
        suffix = Path(urlparse(result.preview_url).path).suffix or ".jpg"
        return self.thumbs_root / f"{result.wallhaven_id}{suffix}"

    def _download_file(self, url: str, destination: Path) -> Path:
        if destination.exists() and destination.stat().st_size > 0:
            return destination
        self._rate_limiter.acquire()
        request = Request(url, headers={"User-Agent": self.user_agent})
        with urlopen(request, timeout=30) as response:
            content = response.read()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return destination

    def _get_json(self, url: str) -> dict:
        self._rate_limiter.acquire()
        request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json"})
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _parse_search_item(self, item: dict) -> WallhavenSearchResult:
        uploader = item.get("uploader") or {}
        thumbs = item.get("thumbs") or {}
        tags = item.get("tags") or []
        return WallhavenSearchResult(
            wallhaven_id=str(item.get("id", "")),
            wallhaven_url=str(item.get("url", "")),
            short_url=str(item.get("short_url", "")),
            image_url=str(item.get("path", "")),
            preview_url=str(thumbs.get("large") or thumbs.get("small") or thumbs.get("original") or item.get("path", "")),
            source_url=item.get("source"),
            uploader=uploader.get("username"),
            category=str(item.get("category", "")),
            purity=str(item.get("purity", "")),
            resolution=str(item.get("resolution", "")),
            ratio=str(item.get("ratio", "")),
            width=int(item["dimension_x"]) if item.get("dimension_x") is not None else None,
            height=int(item["dimension_y"]) if item.get("dimension_y") is not None else None,
            file_size=int(item["file_size"]) if item.get("file_size") is not None else None,
            file_type=item.get("file_type"),
            created_at=item.get("created_at"),
            tags=tuple(str(tag.get("name", "")) for tag in tags if tag.get("name")),
            colors=tuple(str(color) for color in item.get("colors", []) if color),
        )

    def _suffix_from_type(self, file_type: str | None) -> str:
        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }
        return mapping.get((file_type or "").strip().lower(), ".jpg")
