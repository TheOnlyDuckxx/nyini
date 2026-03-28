from __future__ import annotations

from dataclasses import replace

from tests.conftest import create_image
from src.config.settings import AppSettings
from src.domain.enums import Orientation, SmartCollection, SortField


def test_settings_persist_onboarding_and_filter_presets(service_env):
    service, library = service_env
    updated_settings = replace(
        service.settings,
        onboarding_completed=True,
        filter_presets={
            "anime-dark": {
                "search_text": "anime",
                "sort": "rating",
                "orientation": Orientation.LANDSCAPE.value,
                "favorites_only": True,
                "minimum_rating": 4,
                "sidebar_kind": "collection",
                "sidebar_value": SmartCollection.FAVORITES.value,
            }
        },
    )
    service.update_settings(updated_settings)

    reloaded_service = service.create(library_root=library)
    try:
        assert reloaded_service.settings.onboarding_completed is True
        assert "anime-dark" in reloaded_service.settings.filter_presets
        assert reloaded_service.settings.filter_presets["anime-dark"]["sort"] == "rating"
    finally:
        reloaded_service.close()


def test_repository_query_and_migration_foundations(service_env):
    service, library = service_env
    create_image(library / "alpha.jpg", color="red")
    create_image(library / "nested" / "beta.png", size=(900, 1600), color="blue")
    service.scan_library()
    service.update_wallpaper_details(service.list_wallpapers()[0].id or 0, tags=["anime"], notes="dark night", rating=5)

    assert service.count_wallpapers() == 2
    assert len(service.list_wallpapers_page(limit=1, offset=0)) == 1
    assert len(service.list_wallpapers_page(limit=1, offset=1)) == 1

    search_results = service.search_wallpapers(search_text="anime", sort_field=SortField.RATING)
    assert len(search_results) == 1
    assert search_results[0].rating == 5

    portrait_results = service.search_wallpapers(orientation=Orientation.PORTRAIT)
    assert len(portrait_results) == 1
    assert portrait_results[0].orientation == Orientation.PORTRAIT

    migration_versions = {
        int(row["version"])
        for row in service.connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    assert migration_versions >= {1, 2}
