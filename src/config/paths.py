from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess


def _user_dirs_config_path() -> Path:
    config_root = os.environ.get("XDG_CONFIG_HOME")
    if config_root:
        return Path(config_root).expanduser() / "user-dirs.dirs"
    return Path.home() / ".config" / "user-dirs.dirs"


def _xdg_dir(env_name: str, fallback: str) -> Path:
    value = os.environ.get(env_name)
    if value:
        return Path(value).expanduser()
    return Path.home() / fallback


def _expand_shell_path(value: str) -> Path:
    expanded = value.strip().strip('"').replace("$HOME", str(Path.home()))
    return Path(os.path.expandvars(expanded)).expanduser()


def _read_xdg_user_dir(name: str) -> Path | None:
    env_value = os.environ.get(f"XDG_{name}_DIR")
    if env_value:
        return _expand_shell_path(env_value)

    config_path = _user_dirs_config_path()
    if config_path.exists():
        pattern = re.compile(rf'^XDG_{re.escape(name)}_DIR=(.+)$')
        for line in config_path.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line.strip())
            if match:
                return _expand_shell_path(match.group(1))

    if shutil.which("xdg-user-dir"):
        result = subprocess.run(
            ["xdg-user-dir", name],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                return Path(output).expanduser()
    return None


def detect_default_library_root() -> Path:
    pictures_dir = _read_xdg_user_dir("PICTURES") or (Path.home() / "Pictures")
    dedicated_candidates = [
        pictures_dir / "Wallpapers",
        pictures_dir / "wallpapers",
        pictures_dir / "Backgrounds",
        pictures_dir / "backgrounds",
    ]
    for candidate in dedicated_candidates:
        if candidate.exists():
            return candidate
    for candidate in (Path.home() / "Wallpapers", pictures_dir):
        if candidate.exists():
            return candidate
    return pictures_dir / "Wallpapers"


@dataclass(slots=True)
class AppPaths:
    library_root: Path
    data_dir: Path
    cache_dir: Path
    config_dir: Path
    db_path: Path
    thumbnails_dir: Path
    trash_files_dir: Path
    trash_info_dir: Path
    gowall_previews_dir: Path
    gowall_themes_dir: Path
    wallhaven_cache_dir: Path
    mpvpaper_state_path: Path
    config_path: Path

    @classmethod
    def default(cls, library_root: Path | None = None) -> "AppPaths":
        data_dir = _xdg_dir("XDG_DATA_HOME", ".local/share") / "wallmanager"
        cache_dir = _xdg_dir("XDG_CACHE_HOME", ".cache") / "wallmanager"
        config_dir = _xdg_dir("XDG_CONFIG_HOME", ".config") / "wallmanager"
        trash_root = _xdg_dir("XDG_DATA_HOME", ".local/share") / "Trash"
        return cls(
            library_root=(library_root or detect_default_library_root()).expanduser(),
            data_dir=data_dir,
            cache_dir=cache_dir,
            config_dir=config_dir,
            db_path=data_dir / "app.db",
            thumbnails_dir=cache_dir / "thumbnails",
            trash_files_dir=trash_root / "files",
            trash_info_dir=trash_root / "info",
            gowall_previews_dir=cache_dir / "gowall" / "previews",
            gowall_themes_dir=config_dir / "gowall" / "themes",
            wallhaven_cache_dir=cache_dir / "wallhaven",
            mpvpaper_state_path=cache_dir / "mpvpaper" / "active.json",
            config_path=config_dir / "config.toml",
        )

    def ensure_directories(self) -> None:
        for directory in (
            self.library_root,
            self.data_dir,
            self.cache_dir,
            self.config_dir,
            self.thumbnails_dir,
            self.trash_files_dir,
            self.trash_info_dir,
            self.gowall_previews_dir,
            self.gowall_themes_dir,
            self.wallhaven_cache_dir,
            self.mpvpaper_state_path.parent,
        ):
            directory.mkdir(parents=True, exist_ok=True)
