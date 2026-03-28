from __future__ import annotations

from tests.conftest import create_image


def test_update_wallpaper_details_persists_tags_notes_and_rating(service_env):
    service, library = service_env
    create_image(library / "sample.jpg")
    service.scan_library()
    wallpaper = service.list_wallpapers()[0]

    updated = service.update_wallpaper_details(
        wallpaper.id or 0,
        tags=["anime", "dark"],
        notes="favorite night wallpaper",
        rating=4,
    )
    favorited = service.set_favorite(updated.id or 0, True)

    assert favorited.is_favorite is True
    assert favorited.rating == 4
    assert favorited.notes == "favorite night wallpaper"
    assert set(favorited.tags) == {"anime", "dark"}

    reloaded = service.get_wallpaper(favorited.id or 0)
    assert reloaded.is_favorite is True
    assert reloaded.rating == 4
    assert set(reloaded.tags) == {"anime", "dark"}
