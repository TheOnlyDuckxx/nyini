from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest
from PySide6.QtWidgets import QApplication

from src.application.services import WallManagerService


@pytest.fixture(scope="session")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def service_env(tmp_path, monkeypatch):
    xdg_data = tmp_path / "xdg-data"
    xdg_cache = tmp_path / "xdg-cache"
    xdg_config = tmp_path / "xdg-config"
    library = tmp_path / "library"
    library.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data))
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    service = WallManagerService.create(library_root=library)
    try:
        yield service, library
    finally:
        service.close()


def create_image(path: Path, *, size: tuple[int, int] = (1920, 1080), color: str = "red") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color=color)
    image.save(path)
    return path
