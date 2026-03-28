from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtGui import QUndoCommand

from src.application.services import WallManagerService
from src.domain.models import TrashRecord, Wallpaper


RefreshCallback = Callable[[], None]


class ToggleFavoriteCommand(QUndoCommand):
    def __init__(
        self,
        service: WallManagerService,
        wallpaper_id: int,
        refresh_callback: RefreshCallback,
        *,
        value: bool | None = None,
    ) -> None:
        super().__init__("Basculer favori")
        self.service = service
        self.wallpaper_id = wallpaper_id
        self.refresh_callback = refresh_callback
        wallpaper = self.service.get_wallpaper(wallpaper_id)
        self.before = wallpaper.is_favorite
        self.after = (not self.before) if value is None else value

    def redo(self) -> None:
        self.service.set_favorite(self.wallpaper_id, self.after)
        self.refresh_callback()

    def undo(self) -> None:
        self.service.set_favorite(self.wallpaper_id, self.before)
        self.refresh_callback()


class MoveWallpaperCommand(QUndoCommand):
    def __init__(
        self,
        service: WallManagerService,
        wallpaper_id: int,
        destination_dir: Path,
        refresh_callback: RefreshCallback,
        *,
        conflict_strategy: str = "unique",
    ) -> None:
        super().__init__("Deplacer wallpaper")
        self.service = service
        self.wallpaper_id = wallpaper_id
        self.destination_dir = destination_dir
        self.refresh_callback = refresh_callback
        self.conflict_strategy = conflict_strategy
        wallpaper = self.service.get_wallpaper(wallpaper_id)
        self.original_path = wallpaper.path
        self.destination_path: Path | None = None

    def redo(self) -> None:
        if self.destination_path is None:
            moved = self.service.move_wallpaper_to_directory(
                self.wallpaper_id,
                self.destination_dir,
                conflict_strategy=self.conflict_strategy,
            )
            self.destination_path = moved.path
        else:
            self.service.move_wallpaper_to_path(self.wallpaper_id, self.destination_path)
        self.refresh_callback()

    def undo(self) -> None:
        self.service.move_wallpaper_to_path(self.wallpaper_id, self.original_path)
        self.refresh_callback()


class RenameWallpaperCommand(QUndoCommand):
    def __init__(
        self,
        service: WallManagerService,
        wallpaper_id: int,
        template: str,
        refresh_callback: RefreshCallback,
        *,
        index: int | None = None,
        conflict_strategy: str = "unique",
    ) -> None:
        super().__init__("Renommer wallpaper")
        self.service = service
        self.wallpaper_id = wallpaper_id
        self.template = template
        self.refresh_callback = refresh_callback
        self.index = index
        self.conflict_strategy = conflict_strategy
        wallpaper = self.service.get_wallpaper(wallpaper_id)
        self.original_path = wallpaper.path
        self.destination_path: Path | None = None

    def redo(self) -> None:
        if self.destination_path is None:
            renamed = self.service.rename_wallpaper(
                self.wallpaper_id,
                self.template,
                index=self.index,
                conflict_strategy=self.conflict_strategy,
            )
            self.destination_path = renamed.path
        else:
            self.service.move_wallpaper_to_path(self.wallpaper_id, self.destination_path)
        self.refresh_callback()

    def undo(self) -> None:
        self.service.move_wallpaper_to_path(self.wallpaper_id, self.original_path)
        self.refresh_callback()


class TrashWallpaperCommand(QUndoCommand):
    def __init__(
        self,
        service: WallManagerService,
        wallpaper_id: int,
        refresh_callback: RefreshCallback,
    ) -> None:
        super().__init__("Supprimer vers la corbeille")
        self.service = service
        self.refresh_callback = refresh_callback
        self.wallpaper_id = wallpaper_id
        self.snapshot: Wallpaper | None = None
        self.trash_record: TrashRecord | None = None

    def redo(self) -> None:
        snapshot, trash_record = self.service.delete_wallpaper(self.wallpaper_id)
        self.snapshot = snapshot
        self.trash_record = trash_record
        self.refresh_callback()

    def undo(self) -> None:
        if self.snapshot is None or self.trash_record is None:
            raise RuntimeError("Nothing to restore")
        restored = self.service.restore_wallpaper(self.snapshot, self.trash_record)
        self.wallpaper_id = restored.id or self.wallpaper_id
        self.snapshot = restored
        self.refresh_callback()


class UpdateWallpaperDetailsCommand(QUndoCommand):
    def __init__(
        self,
        service: WallManagerService,
        wallpaper_id: int,
        *,
        tags: list[str],
        notes: str,
        rating: int,
        refresh_callback: RefreshCallback,
    ) -> None:
        super().__init__("Modifier details")
        self.service = service
        self.wallpaper_id = wallpaper_id
        self.refresh_callback = refresh_callback
        wallpaper = self.service.get_wallpaper(wallpaper_id)
        self.before_tags = list(wallpaper.tags)
        self.before_notes = wallpaper.notes
        self.before_rating = wallpaper.rating
        self.after_tags = tags
        self.after_notes = notes
        self.after_rating = rating

    def redo(self) -> None:
        self.service.update_wallpaper_details(
            self.wallpaper_id,
            tags=self.after_tags,
            notes=self.after_notes,
            rating=self.after_rating,
        )
        self.refresh_callback()

    def undo(self) -> None:
        self.service.update_wallpaper_details(
            self.wallpaper_id,
            tags=self.before_tags,
            notes=self.before_notes,
            rating=self.before_rating,
        )
        self.refresh_callback()
