from __future__ import annotations

from pathlib import Path

from src.application.services import WallManagerService


def scan_library(service: WallManagerService):
    return service.scan_library()


def open_wallpaper(service: WallManagerService, wallpaper_id: int):
    return service.get_wallpaper(wallpaper_id)


def move_wallpaper(service: WallManagerService, wallpaper_id: int, target_dir: Path):
    return service.move_wallpaper_to_directory(wallpaper_id, target_dir)


def toggle_favorite(service: WallManagerService, wallpaper_id: int):
    return service.toggle_favorite(wallpaper_id)


def delete_wallpaper(service: WallManagerService, wallpaper_id: int):
    return service.delete_wallpaper(wallpaper_id)


def apply_wallpaper(service: WallManagerService, wallpaper_id: int):
    return service.apply_wallpaper(wallpaper_id)
