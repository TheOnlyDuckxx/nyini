from __future__ import annotations

from src.config.paths import AppPaths, detect_default_library_root
from src.infrastructure.wallpaper import backend as backend_module


def test_detect_default_library_root_prefers_xdg_pictures_wallpapers(tmp_path, monkeypatch):
    pictures_dir = tmp_path / "Pictures"
    wallpapers_dir = pictures_dir / "Wallpapers"
    wallpapers_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_PICTURES_DIR", str(pictures_dir))

    detected = detect_default_library_root()
    paths = AppPaths.default()

    assert detected == wallpapers_dir
    assert paths.library_root == wallpapers_dir


def test_auto_backend_detects_gnome_session(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("SWAYSOCK", raising=False)
    monkeypatch.delenv("HYPRLAND_INSTANCE_SIGNATURE", raising=False)
    monkeypatch.setattr(
        backend_module.shutil,
        "which",
        lambda command: "/usr/bin/gsettings" if command == "gsettings" else None,
    )

    backend, status = backend_module.resolve_wallpaper_backend("auto")

    assert backend.backend_id == "gnome"
    assert status.available is True
    assert status.active_id == "gnome"
    assert "GNOME" in status.active_display_name


def test_explicit_backend_falls_back_to_detected_backend(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "XFCE")
    monkeypatch.setattr(
        backend_module.shutil,
        "which",
        lambda command: "/usr/bin/xfconf-query" if command == "xfconf-query" else None,
    )

    backend, status = backend_module.resolve_wallpaper_backend("caelestia")

    assert backend.backend_id == "xfce"
    assert status.available is True
    assert status.active_id == "xfce"
    assert "Bascule automatique" in status.message


def test_service_defaults_to_auto_backend(service_env):
    service, _library = service_env

    status = service.get_wallpaper_backend_status()

    assert service.settings.wallpaper_backend == "auto"
    assert status.preferred_id == "auto"


def test_video_backend_detects_mpvpaper_on_wlroots(monkeypatch, tmp_path):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "sway")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(
        backend_module.shutil,
        "which",
        lambda command: f"/usr/bin/{command}" if command in {"mpvpaper", "mpv"} else None,
    )

    _backend, status = backend_module.resolve_video_wallpaper_backend(tmp_path / "mpvpaper-state.json")

    assert status.available is True
    assert status.active_id == "mpvpaper"
    assert "mpvpaper" in status.message


def test_video_backend_rejects_non_wlroots_wayland(monkeypatch, tmp_path):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setattr(
        backend_module.shutil,
        "which",
        lambda command: f"/usr/bin/{command}" if command in {"mpvpaper", "mpv"} else None,
    )

    _backend, status = backend_module.resolve_video_wallpaper_backend(tmp_path / "mpvpaper-state.json")

    assert status.available is False
    assert "wlroots" in status.message
