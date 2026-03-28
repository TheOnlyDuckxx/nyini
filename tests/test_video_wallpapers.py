from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.domain.enums import MediaKind, SmartCollection
from src.infrastructure.wallpaper.backend import MpvpaperWallpaperBackend


def create_image(path: Path, *, size: tuple[int, int] = (1920, 1080), color: str = "red") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color=color)
    image.save(path)
    return path


def create_dummy_video(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not-a-real-video")
    return path


class _FakeImageBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str | None]] = []

    def apply(self, path: Path, monitor: str | None = None) -> None:
        self.calls.append((path, monitor))


class _FakeVideoBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[Path, str, str | None]] = []
        self.stop_calls = 0

    def apply(self, path: Path, *, preset: str = "video", monitor: str | None = None) -> None:
        self.calls.append((path, preset, monitor))

    def stop(self) -> None:
        self.stop_calls += 1


def test_scan_library_indexes_video_wallpapers(service_env):
    service, library = service_env
    image_path = library / "still.jpg"
    video_path = library / "loop.mp4"

    create_image(image_path)
    create_dummy_video(video_path)

    summary = service.scan_library()
    wallpapers = service.list_wallpapers()
    video = next(wallpaper for wallpaper in wallpapers if wallpaper.path == video_path)
    videos = service.wallpapers_for_collection(SmartCollection.VIDEOS)

    assert summary.scanned_count == 2
    assert video.media_kind is MediaKind.VIDEO
    assert video.thumbnail_path is not None and video.thumbnail_path.exists()
    assert [wallpaper.id for wallpaper in videos] == [video.id]


def test_apply_wallpaper_routes_video_to_mpvpaper_backend(service_env):
    service, library = service_env
    image_path = library / "still.jpg"
    video_path = library / "loop.mp4"

    create_image(image_path)
    create_dummy_video(video_path)
    service.scan_library()
    wallpapers = service.list_wallpapers()
    image = next(wallpaper for wallpaper in wallpapers if wallpaper.path == image_path)
    video = next(wallpaper for wallpaper in wallpapers if wallpaper.path == video_path)

    image_backend = _FakeImageBackend()
    video_backend = _FakeVideoBackend()
    service.wallpaper_backend = image_backend
    service.video_wallpaper_backend = video_backend
    service.settings.mpvpaper_preset = "silent"

    service.apply_wallpaper(video.id or 0)
    service.apply_wallpaper(image.id or 0)

    assert video_backend.calls == [(video_path, "silent", None)]
    assert video_backend.stop_calls == 1
    assert image_backend.calls == [(image_path, None)]


def test_video_settings_are_persisted(service_env):
    service, _library = service_env

    service.settings.animated_video_previews = False
    service.settings.mpvpaper_preset = "pause"
    service.persist_settings()
    reloaded = service.settings_manager.load()

    assert reloaded.animated_video_previews is False
    assert reloaded.mpvpaper_preset == "pause"


def test_mpvpaper_uses_cover_mode(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    class _Process:
        pid = 4242

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _Process()

    monkeypatch.setattr("src.infrastructure.wallpaper.backend.subprocess.Popen", fake_popen)
    backend = MpvpaperWallpaperBackend(tmp_path / "active.json")

    backend.apply(tmp_path / "loop.mp4", preset="silent")

    command = captured["command"]
    assert command[:2] == ["mpvpaper", "-o"]
    assert "panscan=1.0" in command[2]
    assert "loop-file=inf" in command[2]
    assert "no-audio" in command[2]
    assert "," not in command[2]
