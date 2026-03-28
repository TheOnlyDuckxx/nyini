from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from src.domain.models import GowallPreviewResult, GowallStatus, GowallTheme, Wallpaper
from src.i18n import tr


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "theme"


def _load_theme_payload(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Theme JSON invalide: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Theme JSON invalide: {path.name}")
    colors = payload.get("colors")
    if not isinstance(colors, list) or not colors:
        raise ValueError(f"Theme JSON invalide: {path.name}")
    return payload


@dataclass(slots=True)
class GowallClient:
    previews_root: Path
    imported_themes_root: Path
    executable_name: str = "gowall"

    def status(self) -> GowallStatus:
        executable = shutil.which(self.executable_name)
        if executable is None:
            return GowallStatus(
                installed=False,
                version=None,
                executable_path=None,
                message=tr("gowall n'est pas installe. Installe-le pour utiliser les themes."),
            )
        version = None
        try:
            result = subprocess.run(
                [executable, "-v"],
                check=True,
                capture_output=True,
                text=True,
            )
            version_text = result.stdout.strip() or result.stderr.strip()
            if ":" in version_text:
                version = version_text.split(":", 1)[1].strip()
            elif version_text:
                version = version_text
        except subprocess.SubprocessError:
            version = None
        message = tr("gowall disponible ({version})", version=version) if version else tr("gowall disponible")
        return GowallStatus(
            installed=True,
            version=version,
            executable_path=Path(executable),
            message=message,
        )

    def list_themes(self) -> list[GowallTheme]:
        themes: list[GowallTheme] = []
        status = self.status()
        if status.installed and status.executable_path is not None:
            result = subprocess.run(
                [str(status.executable_path), "list"],
                check=True,
                capture_output=True,
                text=True,
            )
            for raw_name in result.stdout.splitlines():
                theme_name = raw_name.strip()
                if not theme_name:
                    continue
                themes.append(
                    GowallTheme(
                        id=f"gowall:{theme_name}",
                        display_name=theme_name,
                        source_kind="gowall_name",
                        theme_arg=theme_name,
                        origin_label="Gowall",
                    )
                )

        themes.extend(self.list_imported_themes())
        deduped: dict[str, GowallTheme] = {theme.id: theme for theme in themes}
        return list(deduped.values())

    def list_imported_themes(self) -> list[GowallTheme]:
        imported: list[GowallTheme] = []
        for path in sorted(self.imported_themes_root.glob("*.json")):
            imported.append(self._theme_from_json_file(path))
        return imported

    def import_theme_json(self, path: Path, *, overwrite: bool = False) -> GowallTheme:
        path = path.expanduser().resolve()
        payload = _load_theme_payload(path)
        display_name = str(payload.get("name") or path.stem)
        slug = _slugify(display_name)
        destination = self.imported_themes_root / f"{slug}.json"
        if destination.exists() and destination.resolve() == path.resolve():
            return self._theme_from_json_file(destination)
        if destination.exists() and not overwrite:
            raise FileExistsError(destination)
        self.imported_themes_root.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        return self._theme_from_json_file(destination)

    def theme_by_id(self, theme_id: str) -> GowallTheme | None:
        for theme in self.list_themes():
            if theme.id == theme_id:
                return theme
        return None

    def preview_path_for(self, wallpaper: Wallpaper, theme: GowallTheme) -> Path:
        fingerprint = hashlib.sha1(
            f"{wallpaper.path}|{wallpaper.mtime}|{wallpaper.size_bytes}".encode("utf-8")
        ).hexdigest()[:16]
        directory = self.previews_root / fingerprint
        filename = f"{_slugify(theme.id)}.png"
        return directory / filename

    def ensure_preview(self, wallpaper: Wallpaper, theme: GowallTheme) -> GowallPreviewResult:
        status = self.status()
        if not status.installed or status.executable_path is None:
            raise RuntimeError(status.message)
        output_path = self.preview_path_for(wallpaper, theme)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if not output_path.exists():
            subprocess.run(
                [
                    str(status.executable_path),
                    "convert",
                    str(wallpaper.path),
                    "--theme",
                    theme.theme_arg,
                    "--format",
                    "png",
                    "--output",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=self._command_env(),
            )
        if not output_path.exists():
            raise RuntimeError(f"Preview gowall absente apres conversion: {theme.display_name}")
        return GowallPreviewResult(
            theme_id=theme.id,
            preview_path=output_path,
            display_name=theme.display_name,
        )

    def _theme_from_json_file(self, path: Path) -> GowallTheme:
        payload = _load_theme_payload(path)
        display_name = str(payload.get("name") or path.stem)
        return GowallTheme(
            id=f"json:{path.stem}",
            display_name=display_name,
            source_kind="json_file",
            theme_arg=str(path),
            origin_label=tr("Importe"),
        )

    def _command_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["HOME"] = str(self._runtime_home_root())
        self._ensure_runtime_config()
        return env

    def _runtime_home_root(self) -> Path:
        return self.previews_root.parent / "runtime-config"

    def _ensure_runtime_config(self) -> None:
        config_root = self._runtime_home_root()
        gowall_dir = config_root / ".config" / "gowall"
        gowall_dir.mkdir(parents=True, exist_ok=True)
        config_path = gowall_dir / "config.yml"
        source_path = self._source_config_path()
        lines: list[str] = []
        if source_path.exists():
            lines = source_path.read_text(encoding="utf-8").splitlines()
        filtered = [
            line
            for line in lines
            if not line.lstrip().startswith("EnableImagePreviewing:")
            and not line.lstrip().startswith("InlineImagePreview:")
        ]
        content_lines = [
            "EnableImagePreviewing: false",
            "InlineImagePreview: false",
            *filtered,
        ]
        config_path.write_text("\n".join(content_lines).rstrip() + "\n", encoding="utf-8")

    def _source_config_path(self) -> Path:
        return Path.home() / ".config" / "gowall" / "config.yml"
