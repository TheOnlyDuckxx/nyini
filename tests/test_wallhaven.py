from __future__ import annotations

from pathlib import Path

from tests.conftest import create_image
from tests.test_gowall import install_fake_gowall
from src.app import create_application
from src.domain.enums import WallpaperSourceKind
from src.domain.models import WallhavenSearchPage, WallhavenSearchRequest, WallhavenSearchResult
from src.ui.dialogs.wallhaven_dialog import WallhavenDialog


class FakeWallhavenClient:
    def __init__(self, tmp_path: Path) -> None:
        self.tmp_path = tmp_path
        self.thumb_path = create_image(tmp_path / "wallhaven-thumb.jpg", size=(480, 270), color="orange")
        self.image_path = create_image(tmp_path / "wallhaven-full.jpg", size=(1920, 1080), color="blue")

    def status(self, api_key: str = ""):
        from src.domain.models import WallhavenStatus

        return WallhavenStatus(
            available=True,
            api_key_configured=bool(api_key),
            message="Wallhaven fake ready",
            rate_limit_per_minute=45,
        )

    def search(self, request: WallhavenSearchRequest, *, api_key: str = "") -> WallhavenSearchPage:
        result = WallhavenSearchResult(
            wallhaven_id="abc123",
            wallhaven_url="https://wallhaven.cc/w/abc123",
            short_url="https://whvn.cc/abc123",
            image_url="https://w.wallhaven.cc/full/ab/wallhaven-abc123.jpg",
            preview_url="https://th.wallhaven.cc/lg/ab/abc123.jpg",
            source_url="https://artist.example/original",
            uploader=None,
            category="anime",
            purity="sfw",
            resolution="1920x1080",
            ratio="16x9",
            width=1920,
            height=1080,
            file_size=123456,
            file_type="image/jpeg",
            created_at="2025-01-01 12:00:00",
            tags=(),
            colors=("#000000", "#ffffff"),
        )
        return WallhavenSearchPage(
            request=request,
            results=(result,),
            current_page=request.page,
            last_page=3,
            total=1,
        )

    def fetch_wallpaper(self, wallhaven_id: str, *, api_key: str = "") -> WallhavenSearchResult:
        return WallhavenSearchResult(
            wallhaven_id=wallhaven_id,
            wallhaven_url=f"https://wallhaven.cc/w/{wallhaven_id}",
            short_url=f"https://whvn.cc/{wallhaven_id}",
            image_url=f"https://w.wallhaven.cc/full/ab/wallhaven-{wallhaven_id}.jpg",
            preview_url="https://th.wallhaven.cc/lg/ab/abc123.jpg",
            source_url="https://artist.example/original",
            uploader="artist42",
            category="anime",
            purity="sfw",
            resolution="1920x1080",
            ratio="16x9",
            width=1920,
            height=1080,
            file_size=123456,
            file_type="image/jpeg",
            created_at="2025-01-01 12:00:00",
            tags=("night sky", "anime girls"),
            colors=("#000000", "#ffffff"),
        )

    def cache_thumbnail(self, result: WallhavenSearchResult) -> Path:
        return self.thumb_path

    def download_image(self, result: WallhavenSearchResult, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"wallhaven-{result.wallhaven_id}.jpg"
        destination.write_bytes(self.image_path.read_bytes())
        return destination


def test_local_scan_backfills_local_provenance(service_env):
    service, library = service_env
    create_image(library / "local.jpg", color="red")

    service.scan_library()
    wallpaper = service.list_wallpapers()[0]

    assert wallpaper.provenance is not None
    assert wallpaper.provenance.source_kind == WallpaperSourceKind.LOCAL


def test_wallhaven_download_imports_provenance_and_history(service_env, tmp_path):
    service, _library = service_env
    service.wallhaven_client = FakeWallhavenClient(tmp_path)

    imported = service.download_wallhaven_results(["abc123"])

    assert len(imported) == 1
    wallpaper = imported[0]
    assert wallpaper.path.exists()
    assert wallpaper.path.parent.name == "Wallhaven"
    assert wallpaper.provenance is not None
    assert wallpaper.provenance.source_kind == WallpaperSourceKind.WALLHAVEN
    assert wallpaper.provenance.remote_id == "abc123"
    assert wallpaper.provenance.author_name == "artist42"
    assert "night sky" in wallpaper.tags
    row = service.connection.execute("SELECT COUNT(*) AS count FROM download_history").fetchone()
    assert int(row["count"]) == 1
    assert service.list_operations()[0].action == "wallhaven_download"


def test_save_gowall_preview_creates_derived_wallpaper(service_env, monkeypatch, tmp_path):
    service, library = service_env
    install_fake_gowall(monkeypatch, tmp_path)
    create_image(library / "original.png", color="purple")
    service.scan_library()
    wallpaper = service.list_wallpapers()[0]
    theme = service.list_gowall_themes()[0]

    saved = service.save_gowall_preview_as_wallpaper(wallpaper.id or 0, theme.id)

    assert saved.path.exists()
    assert "Derived" in saved.path.parts
    assert saved.provenance is not None
    assert saved.provenance.source_kind == WallpaperSourceKind.GOWALL_GENERATED
    assert saved.provenance.parent_wallpaper_id == wallpaper.id


def test_wallhaven_dialog_search_and_import(service_env, qt_app, tmp_path):
    service, library = service_env
    app, window = create_application(library_root=library)
    try:
        window.service.wallhaven_client = FakeWallhavenClient(tmp_path)
        window.thread_pool.waitForDone()
        app.processEvents()

        dialog = WallhavenDialog(window.service, window.job_queue, window)
        window.thread_pool.waitForDone()
        app.processEvents()

        assert dialog.result_list.count() == 1
        dialog.result_list.item(0).setSelected(True)
        dialog.import_selected()
        app.processEvents()

        assert dialog.imported_count == 1

        window.refresh_from_repository()
        window.source_combo.setCurrentIndex(window.source_combo.findData("wallhaven"))
        app.processEvents()

        assert window.proxy.rowCount() == 1
        current = window.proxy.index(0, 0)
        window.grid_view.setCurrentIndex(current)
        window._on_current_proxy_index_changed(current)
        app.processEvents()
        assert window.details.source_kind_label.text() == "Wallhaven"
        assert window.details.author_label.text() == "artist42"
    finally:
        window.close()
        app.processEvents()
