from __future__ import annotations

from dataclasses import replace
import shutil

from tests.conftest import create_image
from src.config.settings import AppSettings
from src.domain.enums import AppLanguage, SortField, ThemeMode


def test_inbox_import_and_duplicate_detection(service_env):
    service, library = service_env
    source = create_image(library / "base.jpg", color="blue")
    inbox_copy = service.settings.inbox_root / "nested" / "base-copy.jpg"
    inbox_copy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, inbox_copy)

    imported_count = service.import_inbox(rescan=False)
    summary = service.scan_library(compute_hashes=True)
    duplicate_groups = service.list_duplicate_groups()

    assert imported_count == 1
    assert summary.scanned_count == 2
    assert not inbox_copy.exists()
    assert (library / "Inbox" / "nested" / "base-copy.jpg").exists()
    assert len(duplicate_groups) == 1
    assert len(duplicate_groups[0].wallpaper_ids) == 2


def test_settings_persist_theme_shortcuts_and_sort(service_env):
    service, library = service_env
    updated_settings = replace(
        service.settings,
        language=AppLanguage.EN,
        theme_mode=ThemeMode.LIGHT,
        default_sort=SortField.NAME,
        auto_import_inbox=True,
        rename_template="{date}_{index}_{stem}",
        shortcuts={**service.settings.shortcuts, "favorite": "Ctrl+Alt+F"},
    )
    service.update_settings(updated_settings)

    reloaded_service = service.create(library_root=library)
    try:
        assert reloaded_service.settings.language == AppLanguage.EN
        assert reloaded_service.settings.theme_mode == ThemeMode.LIGHT
        assert reloaded_service.settings.default_sort == SortField.NAME
        assert reloaded_service.settings.auto_import_inbox is True
        assert reloaded_service.settings.rename_template == "{date}_{index}_{stem}"
        assert reloaded_service.settings.shortcuts["favorite"] == "Ctrl+Alt+F"
    finally:
        reloaded_service.close()


def test_rename_template_is_applied(service_env):
    service, library = service_env
    create_image(library / "rename-me.png", size=(1080, 1920), color="green")
    service.scan_library()
    wallpaper = service.list_wallpapers()[0]

    renamed = service.rename_wallpaper(wallpaper.id or 0, "portrait_{orientation}_{index}", index=3)

    assert renamed.filename == "portrait_portrait_3.png"
    assert renamed.path.exists()
