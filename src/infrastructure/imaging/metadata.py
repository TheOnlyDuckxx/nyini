from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageOps, ImageStat

from src.domain.enums import MediaKind, Orientation


SUPPORTED_IMAGE_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

SUPPORTED_VIDEO_EXTENSIONS = {
    ".avi",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".webm",
}

SUPPORTED_EXTENSIONS = SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_VIDEO_EXTENSIONS


@dataclass(slots=True)
class MediaMetadata:
    media_kind: MediaKind
    width: int | None
    height: int | None
    orientation: Orientation
    aspect_ratio: float | None
    size_bytes: int
    mtime: float
    ctime: float
    brightness: float | None
    avg_color: str | None
    duration_seconds: float | None


def classify_orientation(width: int | None, height: int | None) -> Orientation:
    if not width or not height or width <= 0 or height <= 0:
        return Orientation.UNKNOWN
    if width == height:
        return Orientation.SQUARE
    if width > height:
        return Orientation.LANDSCAPE
    return Orientation.PORTRAIT


def detect_media_kind(path: Path) -> MediaKind:
    return MediaKind.VIDEO if path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS else MediaKind.IMAGE


def extract_media_metadata(path: Path) -> MediaMetadata:
    media_kind = detect_media_kind(path)
    if media_kind is MediaKind.VIDEO:
        return extract_video_metadata(path)
    return extract_image_metadata(path)


def extract_image_metadata(path: Path) -> MediaMetadata:
    stat = path.stat()
    with Image.open(path) as image:
        transposed = ImageOps.exif_transpose(image).convert("RGB")
        width, height = transposed.size
        sample = transposed.copy()
        sample.thumbnail((64, 64))
        color_stats = ImageStat.Stat(sample)
        avg_r, avg_g, avg_b = (int(value) for value in color_stats.mean[:3])
        brightness = float(ImageStat.Stat(sample.convert("L")).mean[0])
    return MediaMetadata(
        media_kind=MediaKind.IMAGE,
        width=width,
        height=height,
        orientation=classify_orientation(width, height),
        aspect_ratio=round(width / height, 4) if height else None,
        size_bytes=stat.st_size,
        mtime=stat.st_mtime,
        ctime=stat.st_ctime,
        brightness=brightness,
        avg_color=f"#{avg_r:02x}{avg_g:02x}{avg_b:02x}",
        duration_seconds=None,
    )


def extract_video_metadata(path: Path) -> MediaMetadata:
    stat = path.stat()
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None

    if shutil.which("ffprobe") is not None:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height:format=duration",
                "-of",
                "json",
                str(path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                payload = {}
            stream = {}
            streams = payload.get("streams")
            if isinstance(streams, list) and streams:
                candidate = streams[0]
                if isinstance(candidate, dict):
                    stream = candidate
            width = _safe_int(stream.get("width"))
            height = _safe_int(stream.get("height"))
            fmt = payload.get("format")
            if isinstance(fmt, dict):
                duration_seconds = _safe_float(fmt.get("duration"))

    return MediaMetadata(
        media_kind=MediaKind.VIDEO,
        width=width,
        height=height,
        orientation=classify_orientation(width, height),
        aspect_ratio=round(width / height, 4) if width and height else None,
        size_bytes=stat.st_size,
        mtime=stat.st_mtime,
        ctime=stat.st_ctime,
        brightness=None,
        avg_color=None,
        duration_seconds=duration_seconds,
    )


def _safe_int(value: object) -> int | None:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _safe_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None
