from __future__ import annotations

import os
from pathlib import Path

from tests.conftest import create_image
from src.app import create_application
from src.ui.dialogs.gowall_theme_dialog import GowallThemeDialog


class FakeWallpaperBackend:
    def __init__(self) -> None:
        self.applied_paths: list[Path] = []

    def apply(self, path: Path, monitor: str | None = None) -> None:
        self.applied_paths.append(path)


def install_fake_gowall(monkeypatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    gowall_script = bin_dir / "gowall"
    gowall_script.write_text(
        """#!/usr/bin/env python3
from os import environ
from pathlib import Path
import shutil
import sys

args = sys.argv[1:]
args_log = environ.get("GOWALL_FAKE_ARGS_LOG")
if args_log:
    with open(args_log, "a", encoding="utf-8") as fh:
        fh.write(" ".join(args) + "\\n")
if not args:
    raise SystemExit(0)
if args[0] in {"-v", "--version"}:
    print("gowall version: v9.9.9")
    raise SystemExit(0)
if args[0] == "list":
    if len(args) >= 3 and args[1] in {"-t", "--theme"}:
        print("#111111")
        print("#222222")
        raise SystemExit(0)
    print("dracula")
    print("nord")
    raise SystemExit(0)
if args[0] == "convert":
    index = 1
    while index < len(args) and args[index] in {"--preview"}:
        index += 2
    input_path = Path(args[index])
    output = None
    fmt = "png"
    index += 1
    while index < len(args):
        token = args[index]
        if token == "--preview":
            index += 2
            continue
        if token in {"-t", "--theme"}:
            index += 2
            continue
        if token in {"-f", "--format"}:
            fmt = args[index + 1]
            index += 2
            continue
        if token == "--output":
            output = Path(args[index + 1])
            index += 2
            continue
        index += 1
    if output is None:
        raise SystemExit(2)
    if output.suffix:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, output)
    else:
        output.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, output / f"{input_path.stem}.{fmt}")
    print(f"saved in {output}")
    raise SystemExit(0)
raise SystemExit(1)
""",
        encoding="utf-8",
    )
    gowall_script.chmod(0o755)

    caelestia_script = bin_dir / "caelestia"
    caelestia_script.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    caelestia_script.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")


def test_gowall_status_listing_and_import(service_env, monkeypatch, tmp_path):
    service, library = service_env
    install_fake_gowall(monkeypatch, tmp_path)

    status = service.get_gowall_status()
    assert status.installed is True
    assert status.version == "v9.9.9"

    theme_json = tmp_path / "custom-theme.json"
    theme_json.write_text('{"name": "My Theme", "colors": ["#111111", "#eeeeee"]}', encoding="utf-8")
    imported = service.import_gowall_theme_json(theme_json)
    themes = service.list_gowall_themes()

    assert any(theme.id == "gowall:dracula" for theme in themes)
    assert any(theme.id == imported.id for theme in themes)

    other_theme_json = tmp_path / "custom-theme-2.json"
    other_theme_json.write_text('{"name": "My Theme", "colors": ["#222222", "#dddddd"]}', encoding="utf-8")
    try:
        service.import_gowall_theme_json(other_theme_json)
    except FileExistsError:
        pass
    else:
        raise AssertionError("Expected a FileExistsError when importing a colliding theme")


def test_gowall_preview_generation_and_apply(service_env, monkeypatch, tmp_path):
    service, library = service_env
    install_fake_gowall(monkeypatch, tmp_path)
    create_image(library / "preview-source.png", color="purple")
    service.scan_library()
    wallpaper = service.list_wallpapers()[0]
    backend = FakeWallpaperBackend()
    service.wallpaper_backend = backend

    previews = service.generate_gowall_previews(wallpaper.id or 0)
    assert len(previews) == 2
    assert all(result.preview_path.exists() for result in previews)

    repeated = service.generate_gowall_previews(wallpaper.id or 0, [previews[0].theme_id])
    assert repeated[0].preview_path == previews[0].preview_path

    applied_path = service.apply_gowall_theme(wallpaper.id or 0, previews[0].theme_id)
    assert applied_path.exists()
    assert backend.applied_paths[-1] == applied_path
    assert service.list_operations()[0].action == "apply_gowall_theme"


def test_gowall_preview_runtime_config_disables_external_preview(service_env, monkeypatch, tmp_path):
    service, library = service_env
    install_fake_gowall(monkeypatch, tmp_path)
    create_image(library / "config-source.png", color="teal")
    service.scan_library()
    wallpaper = service.list_wallpapers()[0]
    theme = service.list_gowall_themes()[0]

    source_home = tmp_path / "home"
    source_config = source_home / ".config" / "gowall" / "config.yml"
    source_config.parent.mkdir(parents=True, exist_ok=True)
    source_config.write_text(
        "EnableImagePreviewing: true\nInlineImagePreview: true\nBackend: swww\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(source_home))

    preview = service.gowall_client.ensure_preview(wallpaper, theme)
    assert preview.preview_path.exists()

    runtime_config = service.gowall_client._runtime_home_root() / ".config" / "gowall" / "config.yml"
    content = runtime_config.read_text(encoding="utf-8")
    assert "EnableImagePreviewing: false" in content
    assert "InlineImagePreview: false" in content
    assert "EnableImagePreviewing: true" not in content
    assert "InlineImagePreview: true" not in content
    assert "Backend: swww" in content


def test_gowall_action_disabled_when_missing(service_env, qt_app, monkeypatch):
    service, library = service_env
    create_image(library / "ui.jpg", color="orange")

    from src.infrastructure.gowall import client as gowall_client_module

    monkeypatch.setattr(gowall_client_module.shutil, "which", lambda _name: None)
    app, window = create_application(library_root=library)
    try:
        window.thread_pool.waitForDone()
        app.processEvents()

        assert window.gowall_action.isEnabled() is False
        assert window.viewer.gowall_button.isEnabled() is False
    finally:
        window.close()
        app.processEvents()


def test_gowall_dialog_generates_previews_and_applies(service_env, qt_app, monkeypatch, tmp_path):
    service, library = service_env
    install_fake_gowall(monkeypatch, tmp_path)
    create_image(library / "gallery.png", color="blue")

    app, window = create_application(library_root=library)
    try:
        window.service.wallpaper_backend = FakeWallpaperBackend()
        window.thread_pool.waitForDone()
        app.processEvents()

        dialog = GowallThemeDialog(window.service, window.job_queue, window.current_wallpaper(), window)
        window.thread_pool.waitForDone()
        app.processEvents()

        assert dialog.theme_list.count() == 2
        assert dialog.theme_list.currentItem() is not None
        preview_path = dialog.theme_list.currentItem().data(GowallThemeDialog.PREVIEW_PATH_ROLE)
        assert isinstance(preview_path, str)
        assert Path(preview_path).exists()

        theme_json = tmp_path / "imported.json"
        theme_json.write_text('{"name": "Rose Test", "colors": ["#111111", "#eeeeee"]}', encoding="utf-8")
        monkeypatch.setattr(
            "src.ui.dialogs.gowall_theme_dialog.QFileDialog.getOpenFileName",
            lambda *args, **kwargs: (str(theme_json), "Themes JSON (*.json)"),
        )
        dialog.import_theme_json()
        window.thread_pool.waitForDone()
        app.processEvents()

        assert dialog.theme_list.count() == 3

        dialog.theme_list.setCurrentRow(0)
        dialog.apply_selected_theme()
        app.processEvents()

        assert dialog.applied_output_path is not None
        assert dialog.applied_output_path.exists()
        assert window.service.wallpaper_backend.applied_paths[-1] == dialog.applied_output_path
    finally:
        window.close()
        app.processEvents()
