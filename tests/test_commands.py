from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QUndoStack

from tests.conftest import create_image
from src.application.commands import MoveWallpaperCommand, ToggleFavoriteCommand, TrashWallpaperCommand


def test_commands_support_undo_redo(service_env, qt_app):
    service, library = service_env
    source = create_image(library / "command.jpg")
    service.scan_library()
    wallpaper = service.list_wallpapers()[0]
    target_dir = library / "favorites"
    target_dir.mkdir()

    stack = QUndoStack()
    refresh_calls: list[str] = []

    def refresh():
        refresh_calls.append("refresh")

    stack.push(ToggleFavoriteCommand(service, wallpaper.id or 0, refresh))
    assert service.get_wallpaper(wallpaper.id or 0).is_favorite is True
    stack.undo()
    assert service.get_wallpaper(wallpaper.id or 0).is_favorite is False
    stack.redo()
    assert service.get_wallpaper(wallpaper.id or 0).is_favorite is True

    stack.push(MoveWallpaperCommand(service, wallpaper.id or 0, target_dir, refresh))
    moved = service.get_wallpaper(wallpaper.id or 0)
    assert moved.path.parent == target_dir
    assert moved.path.exists()
    stack.undo()
    moved_back = service.get_wallpaper(wallpaper.id or 0)
    assert moved_back.path == source
    assert moved_back.path.exists()
    stack.redo()
    moved_again = service.get_wallpaper(wallpaper.id or 0)
    assert moved_again.path.parent == target_dir

    stack.push(TrashWallpaperCommand(service, wallpaper.id or 0, refresh))
    assert service.list_wallpapers() == []
    stack.undo()
    restored = service.list_wallpapers()[0]
    assert restored.path.exists()
    assert restored.filename == Path(restored.path).name
    assert refresh_calls
