from __future__ import annotations

from tests.conftest import create_image


def test_scan_library_indexes_supported_images(service_env):
    service, library = service_env
    create_image(library / "one.jpg")
    create_image(library / "nested" / "two.png", size=(900, 1600), color="blue")
    (library / "ignore.txt").write_text("nope", encoding="utf-8")

    summary = service.scan_library()
    wallpapers = service.list_wallpapers()

    assert summary.scanned_count == 2
    assert summary.imported_count == 2
    assert len(wallpapers) == 2
    assert all(wallpaper.thumbnail_path and wallpaper.thumbnail_path.exists() for wallpaper in wallpapers)
    assert {wallpaper.orientation.value for wallpaper in wallpapers} == {"landscape", "portrait"}
