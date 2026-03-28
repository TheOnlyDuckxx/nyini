from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import tomllib

from src.config.paths import AppPaths
from src.config.shortcuts import default_shortcut_map
from src.domain.enums import AppLanguage, SortField, ThemeMode


@dataclass(slots=True)
class AppSettings:
    library_root: Path
    inbox_root: Path
    language: AppLanguage = AppLanguage.FR
    thumbnail_size: int = 256
    layout_preset: str = "balanced"
    show_sidebar: bool = True
    show_details: bool = True
    polling_interval_ms: int = 5000
    wallpaper_backend: str = "auto"
    default_sort: SortField = SortField.MTIME
    compute_hashes_on_scan: bool = False
    auto_import_inbox: bool = False
    rename_template: str = "{stem}"
    slideshow_interval_seconds: int = 8
    theme_mode: ThemeMode = ThemeMode.AUTO
    shortcuts: dict[str, str] = field(default_factory=default_shortcut_map)
    onboarding_completed: bool = False
    filter_presets: dict[str, dict[str, str | int | bool | None]] = field(default_factory=dict)
    animated_video_previews: bool = True
    mpvpaper_preset: str = "video"
    wallhaven_api_key: str = ""
    wallhaven_default_purity: str = "100"
    wallhaven_default_ratios: str = ""
    wallhaven_default_atleast: str = ""
    wallhaven_default_blacklist: str = ""


def _coerce_sort_field(value: SortField | str) -> SortField:
    return value if isinstance(value, SortField) else SortField(str(value))


def _coerce_theme_mode(value: ThemeMode | str) -> ThemeMode:
    return value if isinstance(value, ThemeMode) else ThemeMode(str(value))


def _coerce_language(value: AppLanguage | str) -> AppLanguage:
    return value if isinstance(value, AppLanguage) else AppLanguage(str(value))


class SettingsManager:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load(self) -> AppSettings:
        if not self.paths.config_path.exists():
            settings = AppSettings(
                library_root=self.paths.library_root,
                inbox_root=self.paths.library_root / "_Inbox",
            )
            self.save(settings)
            return settings

        with self.paths.config_path.open("rb") as handle:
            raw = tomllib.load(handle)

        app = raw.get("app", {})
        library_root = Path(app.get("library_root", str(self.paths.library_root))).expanduser()
        inbox_root = Path(app.get("inbox_root", str(library_root / "_Inbox"))).expanduser()
        shortcuts = default_shortcut_map()
        shortcuts.update({str(key): str(value) for key, value in raw.get("shortcuts", {}).items()})
        filter_presets: dict[str, dict[str, str | int | bool | None]] = {}
        for name, payload in raw.get("filter_presets", {}).items():
            if isinstance(payload, dict):
                filter_presets[str(name)] = {str(key): value for key, value in payload.items()}
                continue
            if not isinstance(payload, str):
                continue
            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict):
                filter_presets[str(name)] = {str(key): value for key, value in decoded.items()}
        return AppSettings(
            library_root=library_root,
            inbox_root=inbox_root,
            language=AppLanguage(str(app.get("language", AppLanguage.FR.value))),
            thumbnail_size=int(app.get("thumbnail_size", 256)),
            layout_preset=str(app.get("layout_preset", "balanced")),
            show_sidebar=bool(app.get("show_sidebar", True)),
            show_details=bool(app.get("show_details", True)),
            polling_interval_ms=int(app.get("polling_interval_ms", 5000)),
            wallpaper_backend=str(app.get("wallpaper_backend", "auto")),
            default_sort=SortField(str(app.get("default_sort", SortField.MTIME.value))),
            compute_hashes_on_scan=bool(app.get("compute_hashes_on_scan", False)),
            auto_import_inbox=bool(app.get("auto_import_inbox", False)),
            rename_template=str(app.get("rename_template", "{stem}")),
            slideshow_interval_seconds=max(1, int(app.get("slideshow_interval_seconds", 8))),
            theme_mode=ThemeMode(str(app.get("theme_mode", ThemeMode.AUTO.value))),
            shortcuts=shortcuts,
            onboarding_completed=bool(app.get("onboarding_completed", False)),
            filter_presets=filter_presets,
            animated_video_previews=bool(app.get("animated_video_previews", True)),
            mpvpaper_preset=str(app.get("mpvpaper_preset", "video")),
            wallhaven_api_key=str(app.get("wallhaven_api_key", "")),
            wallhaven_default_purity=str(app.get("wallhaven_default_purity", "100")),
            wallhaven_default_ratios=str(app.get("wallhaven_default_ratios", "")),
            wallhaven_default_atleast=str(app.get("wallhaven_default_atleast", "")),
            wallhaven_default_blacklist=str(app.get("wallhaven_default_blacklist", "")),
        )

    def save(self, settings: AppSettings) -> None:
        self.paths.config_dir.mkdir(parents=True, exist_ok=True)
        default_sort = _coerce_sort_field(settings.default_sort)
        theme_mode = _coerce_theme_mode(settings.theme_mode)
        language = _coerce_language(settings.language)
        def _escape(value: str) -> str:
            return value.replace("\\", "\\\\").replace('"', '\\"')
        content_lines = [
            "[app]",
            f'library_root = "{settings.library_root}"',
            f'inbox_root = "{settings.inbox_root}"',
            f'language = "{language.value}"',
            f"thumbnail_size = {settings.thumbnail_size}",
            f'layout_preset = "{settings.layout_preset}"',
            f"show_sidebar = {str(settings.show_sidebar).lower()}",
            f"show_details = {str(settings.show_details).lower()}",
            f"polling_interval_ms = {settings.polling_interval_ms}",
            f'wallpaper_backend = "{settings.wallpaper_backend}"',
            f'default_sort = "{default_sort.value}"',
            f"compute_hashes_on_scan = {str(settings.compute_hashes_on_scan).lower()}",
            f"auto_import_inbox = {str(settings.auto_import_inbox).lower()}",
            f'rename_template = "{_escape(settings.rename_template)}"',
            f"slideshow_interval_seconds = {settings.slideshow_interval_seconds}",
            f'theme_mode = "{theme_mode.value}"',
            f"onboarding_completed = {str(settings.onboarding_completed).lower()}",
            f"animated_video_previews = {str(settings.animated_video_previews).lower()}",
            f'mpvpaper_preset = "{_escape(settings.mpvpaper_preset)}"',
            f'wallhaven_api_key = "{_escape(settings.wallhaven_api_key)}"',
            f'wallhaven_default_purity = "{_escape(settings.wallhaven_default_purity)}"',
            f'wallhaven_default_ratios = "{_escape(settings.wallhaven_default_ratios)}"',
            f'wallhaven_default_atleast = "{_escape(settings.wallhaven_default_atleast)}"',
            f'wallhaven_default_blacklist = "{_escape(settings.wallhaven_default_blacklist)}"',
            "",
            "[shortcuts]",
        ]
        for action_id, sequence in sorted(settings.shortcuts.items()):
            escaped = _escape(sequence)
            content_lines.append(f'{action_id} = "{escaped}"')
        if settings.filter_presets:
            content_lines.extend(["", "[filter_presets]"])
            for preset_name, preset_data in sorted(settings.filter_presets.items()):
                escaped_name = _escape(preset_name)
                payload = json.dumps(preset_data, ensure_ascii=False, sort_keys=True)
                escaped_payload = _escape(payload)
                content_lines.append(f'"{escaped_name}" = "{escaped_payload}"')
        content_lines.append("")
        content = "\n".join(content_lines)
        self.paths.config_path.write_text(content, encoding="utf-8")
