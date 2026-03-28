from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDockWidget

from tests.conftest import create_image
from src.app import create_application
from src.domain.enums import SortField


def test_multi_selection_bar_and_clear_filters(service_env, qt_app):
    service, library = service_env
    create_image(library / "one.jpg", color="red")
    create_image(library / "two.jpg", color="blue")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        first = window.proxy.index(0, 0)
        second = window.proxy.index(1, 0)
        window.grid_view.setCurrentIndex(first)
        window.grid_view.selectionModel().select(
            first,
            QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
        )
        window.grid_view.selectionModel().select(
            second,
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
        app.processEvents()

        assert not window.selection_bar.isHidden()
        assert window.selection_count_label.text() == "2 wallpapers selectionnes"

        window.search_input.setText("one")
        window.favorites_only_checkbox.setChecked(True)
        app.processEvents()

        assert not window.filter_chips_bar.isHidden()

        window.clear_filters()
        app.processEvents()

        assert window.search_input.text() == ""
        assert window.favorites_only_checkbox.isChecked() is False
        assert window.minimum_rating_spin.value() == 0
    finally:
        window.close()
        app.processEvents()


def test_review_inbox_switches_to_viewer(service_env, qt_app):
    service, library = service_env
    create_image(library / "_Inbox" / "review-me.jpg", color="green")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        window.show_inbox_review()
        app.processEvents()

        assert window.current_sidebar_selection == ("collection", "inbox")
        assert window.stack.currentWidget() is window.viewer
        assert window.status_location_label.text() == "Collection: Inbox"
    finally:
        window.close()
        app.processEvents()


def test_quick_preview_uses_viewer_without_losing_grid_context(service_env, qt_app):
    service, library = service_env
    create_image(library / "preview.jpg", color="purple")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        current = window.proxy.index(0, 0)
        window.grid_view.setCurrentIndex(current)
        window.show_quick_preview(current)
        app.processEvents()

        assert window.stack.currentWidget() is window.viewer
        assert window.viewer.wallpaper is not None

        window.show_grid()
        app.processEvents()

        assert window.stack.currentWidget() is window.grid_view
    finally:
        window.close()
        app.processEvents()


def test_layout_controls_and_thumbnail_density(service_env, qt_app):
    service, library = service_env
    create_image(library / "layout.jpg", color="orange")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        assert not window.sidebar_dock.isHidden()
        assert not window.details_dock.isHidden()
        assert window.sidebar_dock.features() == QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        assert window.details_dock.features() == QDockWidget.DockWidgetFeature.NoDockWidgetFeatures

        base_size = window.grid_view.iconSize().width()
        window._change_thumbnail_density(1)
        app.processEvents()

        assert window.grid_view.iconSize().width() == base_size + 16
        assert window.thumbnail_size_label.text().endswith("px")

        window._apply_layout_preset("focus")
        app.processEvents()
        assert window.sidebar_dock.isHidden()
        assert window.details_dock.isHidden()

        window._apply_layout_preset("balanced")
        app.processEvents()
        assert not window.sidebar_dock.isHidden()
        assert not window.details_dock.isHidden()
    finally:
        window.close()
        app.processEvents()


def test_sidebar_filter_is_interactive(service_env, qt_app):
    service, library = service_env
    create_image(library / "land" / "one.jpg", color="red")
    create_image(library / "portrait" / "two.jpg", color="blue")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        window.sidebar.filter_input.setText("port")
        QTest.qWait(50)
        app.processEvents()

        visibility_by_label = {item.text(0): item.isHidden() for item in window.sidebar._iter_items()}
        assert visibility_by_label["portrait"] is False
        assert visibility_by_label["land"] is True
    finally:
        window.close()
        app.processEvents()


def test_viewer_refresh_after_action_keeps_app_stable(service_env, qt_app):
    service, library = service_env
    create_image(library / "one.jpg", color="red")
    create_image(library / "two.jpg", color="blue")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        current = window.proxy.index(0, 0)
        window.grid_view.setCurrentIndex(current)
        window.open_current_in_viewer(current)
        app.processEvents()

        window.toggle_selected_favorite()
        app.processEvents()

        assert window.stack.currentWidget() is window.viewer
        assert window.current_wallpaper() is not None
        assert window.current_wallpaper().is_favorite is True

        window.delete_selected_wallpapers()
        app.processEvents()

        assert window.model.rowCount() == 1
        assert window.stack.currentWidget() is window.viewer
        assert window.current_wallpaper() is not None
    finally:
        window.close()
        app.processEvents()


def test_viewer_can_close_immediately_after_open(service_env, qt_app):
    service, library = service_env
    create_image(library / "one.jpg", color="red")
    create_image(library / "two.jpg", color="blue")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        current = window.proxy.index(0, 0)
        window.grid_view.setCurrentIndex(current)
        window.open_current_in_viewer(current)
        app.processEvents()

        assert window.stack.currentWidget() is window.viewer

        window.close()
        app.processEvents()
    finally:
        app.processEvents()


def test_viewer_delete_advances_to_next_item(service_env, qt_app):
    service, library = service_env
    create_image(library / "a.jpg", color="red")
    create_image(library / "b.jpg", color="green")
    create_image(library / "c.jpg", color="blue")

    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        window.sort_combo.setCurrentIndex(window.sort_combo.findData(SortField.NAME))
        window._on_sort_changed()
        app.processEvents()

        current = window.proxy.index(1, 0)
        window.grid_view.setCurrentIndex(current)
        window.open_current_in_viewer(current)
        app.processEvents()

        assert window.current_wallpaper() is not None
        assert window.current_wallpaper().filename == "b.jpg"

        window.delete_selected_wallpapers()
        app.processEvents()

        assert window.stack.currentWidget() is window.viewer
        assert window.current_wallpaper() is not None
        assert window.current_wallpaper().filename == "c.jpg"
    finally:
        window.close()
        app.processEvents()
