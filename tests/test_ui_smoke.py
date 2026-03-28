from __future__ import annotations

from dataclasses import replace

from tests.conftest import create_image
from src.app import create_application
from src.domain.enums import AppLanguage


def test_main_window_smoke(service_env, qt_app):
    service, library = service_env
    create_image(library / "ui.jpg")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()
        assert window.windowTitle() == "Nyini"
        assert window.proxy.rowCount() == 1
        assert window.details.wallpaper is not None
        assert window.settings_action is not None
        assert window.shortcuts_help_action is not None
    finally:
        window.close()
        app.processEvents()


def test_main_window_retranslates_when_language_changes(service_env, qt_app):
    service, library = service_env
    create_image(library / "ui-en.jpg")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        window._apply_new_settings(replace(window.service.settings, language=AppLanguage.EN), reset_sidebar=False)
        app.processEvents()

        assert window.search_input.placeholderText() == "Search: name, tags, notes, path"
        assert window.clear_filters_button.text() == "Clear filters"
        assert window.details.info_group.title() == "Metadata"
        assert window.sidebar.tree.topLevelItem(0).text(0) == "Entire library"
    finally:
        window.close()
        app.processEvents()
