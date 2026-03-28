from __future__ import annotations

from abc import ABC, abstractmethod
import json
from pathlib import Path
import os
import shutil
import signal
import subprocess

from src.domain.models import WallpaperBackendOption, WallpaperBackendStatus, VideoWallpaperBackendStatus
from src.i18n import tr


class WallpaperBackend(ABC):
    backend_id = "unknown"
    display_name = "Inconnu"

    @abstractmethod
    def apply(self, path: Path, monitor: str | None = None) -> None:
        raise NotImplementedError


class VideoWallpaperBackend(ABC):
    backend_id = "none"
    display_name = "Aucun backend video"

    @abstractmethod
    def apply(self, path: Path, *, preset: str = "video", monitor: str | None = None) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        return None


def _run_command(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, capture_output=True, text=True)


class CaelestiaWallpaperBackend(WallpaperBackend):
    backend_id = "caelestia"
    display_name = "Caelestia"

    def apply(self, path: Path, monitor: str | None = None) -> None:
        _run_command(["caelestia", "wallpaper", "-f", str(path)])


class PlasmaWallpaperBackend(WallpaperBackend):
    backend_id = "plasma"
    display_name = "KDE Plasma"

    def apply(self, path: Path, monitor: str | None = None) -> None:
        _run_command(["plasma-apply-wallpaperimage", str(path)])


class GSettingsWallpaperBackend(WallpaperBackend):
    def __init__(
        self,
        *,
        backend_id: str,
        display_name: str,
        schema: str,
        key: str,
        dark_key: str | None = None,
    ) -> None:
        self.backend_id = backend_id
        self.display_name = display_name
        self.schema = schema
        self.key = key
        self.dark_key = dark_key

    def apply(self, path: Path, monitor: str | None = None) -> None:
        value = str(path) if self.key.endswith("filename") else path.resolve().as_uri()
        _run_command(["gsettings", "set", self.schema, self.key, value])
        if self.dark_key:
            dark_value = path.resolve().as_uri()
            _run_command(["gsettings", "set", self.schema, self.dark_key, dark_value], check=False)


class XfceWallpaperBackend(WallpaperBackend):
    backend_id = "xfce"
    display_name = "XFCE"

    def apply(self, path: Path, monitor: str | None = None) -> None:
        result = _run_command(["xfconf-query", "--channel", "xfce4-desktop", "--list"])
        properties = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip().endswith("/last-image") or line.strip().endswith("/image-path")
        ]
        if not properties:
            raise RuntimeError("XFCE desktop properties not found")
        for prop in properties:
            _run_command(
                [
                    "xfconf-query",
                    "--channel",
                    "xfce4-desktop",
                    "--property",
                    prop,
                    "--set",
                    str(path),
                ]
            )


class SwayMsgWallpaperBackend(WallpaperBackend):
    backend_id = "swaymsg"
    display_name = "Sway"

    def apply(self, path: Path, monitor: str | None = None) -> None:
        target = monitor or "*"
        _run_command(["swaymsg", "output", target, "bg", str(path), "fill"])


class SwwwWallpaperBackend(WallpaperBackend):
    backend_id = "swww"
    display_name = "swww"

    def apply(self, path: Path, monitor: str | None = None) -> None:
        command = ["swww", "img", str(path)]
        if monitor:
            command.extend(["-o", monitor])
        _run_command(command)


class FehWallpaperBackend(WallpaperBackend):
    backend_id = "feh"
    display_name = "feh"

    def apply(self, path: Path, monitor: str | None = None) -> None:
        _run_command(["feh", "--bg-fill", str(path)])


class NitrogenWallpaperBackend(WallpaperBackend):
    backend_id = "nitrogen"
    display_name = "Nitrogen"

    def apply(self, path: Path, monitor: str | None = None) -> None:
        _run_command(["nitrogen", "--set-zoom-fill", "--save", str(path)])


class NoopWallpaperBackend(WallpaperBackend):
    backend_id = "none"
    display_name = "Aucun backend"

    def __init__(self, message: str = "No supported wallpaper backend available") -> None:
        self.message = message

    def apply(self, path: Path, monitor: str | None = None) -> None:
        raise RuntimeError(self.message)


class MpvpaperWallpaperBackend(VideoWallpaperBackend):
    backend_id = "mpvpaper"
    display_name = "mpvpaper"

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def apply(self, path: Path, *, preset: str = "video", monitor: str | None = None) -> None:
        self.stop()
        target = monitor or "ALL"
        base_options = "loop-file=inf panscan=1.0"
        options = {
            "video": base_options,
            "silent": f"{base_options} no-audio",
            "pause": f"{base_options} no-audio pause=yes",
        }.get((preset or "video").strip().lower(), base_options)
        process = subprocess.Popen(
            [
                "mpvpaper",
                "-o",
                options,
                target,
                str(path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.state_path.write_text(json.dumps({"pid": process.pid}), encoding="utf-8")

    def stop(self) -> None:
        pid = self._read_pid()
        if pid is None:
            return
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass
        try:
            self.state_path.unlink()
        except FileNotFoundError:
            pass

    def _read_pid(self) -> int | None:
        if not self.state_path.exists():
            return None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        value = payload.get("pid")
        if not isinstance(value, int) or value <= 0:
            return None
        return value


class NoopVideoWallpaperBackend(VideoWallpaperBackend):
    def __init__(self, message: str) -> None:
        self.message = message

    def apply(self, path: Path, *, preset: str = "video", monitor: str | None = None) -> None:
        raise RuntimeError(self.message)


def _session_type() -> str:
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def _desktop_tokens() -> set[str]:
    tokens: set[str] = set()
    for env_name in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION", "GDMSESSION"):
        value = os.environ.get(env_name, "")
        for part in value.replace(":", ";").replace(",", ";").split(";"):
            token = part.strip().lower()
            if token:
                tokens.add(token)
    if os.environ.get("KDE_FULL_SESSION"):
        tokens.add("plasma")
        tokens.add("kde")
    if os.environ.get("SWAYSOCK"):
        tokens.add("sway")
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        tokens.add("hyprland")
    return tokens


def _desktop_environment_label(tokens: set[str]) -> str:
    if not tokens:
        return "unknown"
    return ", ".join(sorted(tokens))


def _has_any(tokens: set[str], *values: str) -> bool:
    return any(value in tokens for value in values)


def _is_probably_wlroots(tokens: set[str], session_type: str) -> bool:
    if session_type != "wayland":
        return False
    if _has_any(tokens, "gnome", "ubuntu", "plasma", "kde", "cinnamon", "mate"):
        return False
    return True


def _availability_for_backend(backend_id: str, *, tokens: set[str], session_type: str) -> tuple[bool, str]:
    if backend_id == "plasma":
        available = shutil.which("plasma-apply-wallpaperimage") is not None
        return available, tr("Requiert plasma-apply-wallpaperimage")
    if backend_id in {"gnome", "cinnamon", "mate"}:
        available = shutil.which("gsettings") is not None
        return available, tr("Requiert gsettings")
    if backend_id == "xfce":
        available = shutil.which("xfconf-query") is not None and _has_any(tokens, "xfce")
        return available, tr("Requiert xfconf-query sur une session XFCE")
    if backend_id == "swaymsg":
        available = shutil.which("swaymsg") is not None and _has_any(tokens, "sway")
        return available, tr("Requiert swaymsg sur une session Sway")
    if backend_id == "swww":
        available = shutil.which("swww") is not None and session_type == "wayland"
        return available, tr("Requiert swww sur Wayland")
    if backend_id == "caelestia":
        available = shutil.which("caelestia") is not None
        return available, tr("Requiert l'executable caelestia")
    if backend_id == "feh":
        available = shutil.which("feh") is not None and session_type == "x11"
        return available, tr("Requiert feh sur X11")
    if backend_id == "nitrogen":
        available = shutil.which("nitrogen") is not None and session_type == "x11"
        return available, tr("Requiert nitrogen sur X11")
    return False, tr("Backend inconnu")


def _backend_factory(backend_id: str) -> WallpaperBackend:
    if backend_id == "plasma":
        return PlasmaWallpaperBackend()
    if backend_id == "gnome":
        return GSettingsWallpaperBackend(
            backend_id="gnome",
            display_name="GNOME / Ubuntu",
            schema="org.gnome.desktop.background",
            key="picture-uri",
            dark_key="picture-uri-dark",
        )
    if backend_id == "cinnamon":
        return GSettingsWallpaperBackend(
            backend_id="cinnamon",
            display_name="Cinnamon",
            schema="org.cinnamon.desktop.background",
            key="picture-uri",
        )
    if backend_id == "mate":
        return GSettingsWallpaperBackend(
            backend_id="mate",
            display_name="MATE",
            schema="org.mate.background",
            key="picture-filename",
        )
    if backend_id == "xfce":
        return XfceWallpaperBackend()
    if backend_id == "swaymsg":
        return SwayMsgWallpaperBackend()
    if backend_id == "swww":
        return SwwwWallpaperBackend()
    if backend_id == "caelestia":
        return CaelestiaWallpaperBackend()
    if backend_id == "feh":
        return FehWallpaperBackend()
    if backend_id == "nitrogen":
        return NitrogenWallpaperBackend()
    return NoopWallpaperBackend(f"Unsupported wallpaper backend: {backend_id}")


def _backend_display_name(backend_id: str) -> str:
    return _backend_factory(backend_id).display_name


def _all_backend_ids() -> tuple[str, ...]:
    return ("plasma", "gnome", "cinnamon", "mate", "xfce", "swaymsg", "swww", "caelestia", "feh", "nitrogen")


def _auto_backend_order(tokens: set[str], session_type: str) -> list[str]:
    ordered: list[str] = []

    def add(backend_id: str) -> None:
        if backend_id not in ordered:
            ordered.append(backend_id)

    if _has_any(tokens, "plasma", "kde"):
        add("plasma")
    if _has_any(tokens, "cinnamon"):
        add("cinnamon")
    if _has_any(tokens, "mate"):
        add("mate")
    if _has_any(tokens, "gnome", "ubuntu", "pop", "unity", "pantheon"):
        add("gnome")
    if _has_any(tokens, "xfce"):
        add("xfce")
    if _has_any(tokens, "sway"):
        add("swaymsg")
        add("swww")
    if _has_any(tokens, "hyprland"):
        add("swww")
    if session_type == "wayland":
        add("swww")
    if session_type == "x11":
        add("feh")
        add("nitrogen")
    add("caelestia")

    for backend_id in _all_backend_ids():
        add(backend_id)
    return ordered


def _build_options(tokens: set[str], session_type: str) -> tuple[WallpaperBackendOption, ...]:
    options: list[WallpaperBackendOption] = []
    for backend_id in _auto_backend_order(tokens, session_type):
        available, reason = _availability_for_backend(backend_id, tokens=tokens, session_type=session_type)
        options.append(
            WallpaperBackendOption(
                backend_id=backend_id,
                display_name=_backend_display_name(backend_id),
                available=available,
                reason=reason,
            )
        )
    deduplicated: list[WallpaperBackendOption] = []
    seen: set[str] = set()
    for option in options:
        if option.backend_id in seen:
            continue
        deduplicated.append(option)
        seen.add(option.backend_id)
    return tuple(deduplicated)


def resolve_wallpaper_backend(preferred: str = "auto") -> tuple[WallpaperBackend, WallpaperBackendStatus]:
    normalized_preferred = (preferred or "auto").strip().lower()
    session_type = _session_type()
    desktop_tokens = _desktop_tokens()
    options = _build_options(desktop_tokens, session_type)
    options_by_id = {option.backend_id: option for option in options}

    def build_status(
        *,
        active_backend: WallpaperBackend,
        active_option: WallpaperBackendOption | None,
        available: bool,
        message: str,
    ) -> WallpaperBackendStatus:
        return WallpaperBackendStatus(
            preferred_id=normalized_preferred,
            active_id=active_backend.backend_id,
            active_display_name=active_backend.display_name,
            available=available,
            session_type=session_type,
            desktop_environment=_desktop_environment_label(desktop_tokens),
            message=message,
            options=options,
        )

    auto_candidate = next((option for option in options if option.available), None)
    if normalized_preferred != "auto":
        preferred_option = options_by_id.get(normalized_preferred)
        if preferred_option and preferred_option.available:
            backend = _backend_factory(preferred_option.backend_id)
            message = tr("Backend explicite '{backend_name}' actif.", backend_name=preferred_option.display_name)
            return backend, build_status(
                active_backend=backend,
                active_option=preferred_option,
                available=True,
                message=message,
            )
        if auto_candidate is not None:
            backend = _backend_factory(auto_candidate.backend_id)
            reason = preferred_option.reason if preferred_option is not None else tr("Backend inconnu")
            message = tr(
                "Backend '{backend_id}' indisponible ({reason}). Bascule automatique vers {backend_name}.",
                backend_id=normalized_preferred,
                reason=reason,
                backend_name=auto_candidate.display_name,
            )
            return backend, build_status(
                active_backend=backend,
                active_option=auto_candidate,
                available=True,
                message=message,
            )
        backend = NoopWallpaperBackend(
            f"Wallpaper backend '{normalized_preferred}' unavailable and no automatic fallback found"
        )
        return backend, build_status(
            active_backend=backend,
            active_option=None,
            available=False,
            message=tr("Aucun backend wallpaper disponible pour '{backend_id}'.", backend_id=normalized_preferred),
        )

    if auto_candidate is not None:
        backend = _backend_factory(auto_candidate.backend_id)
        message = tr("Detection automatique: {backend_name}.", backend_name=auto_candidate.display_name)
        return backend, build_status(
            active_backend=backend,
            active_option=auto_candidate,
            available=True,
            message=message,
        )

    backend = NoopWallpaperBackend("No supported wallpaper backend available")
    return backend, build_status(
        active_backend=backend,
        active_option=None,
        available=False,
        message=tr("Aucun backend wallpaper compatible detecte sur ce systeme."),
    )


def detect_wallpaper_backend(preferred: str = "auto") -> WallpaperBackend:
    return resolve_wallpaper_backend(preferred)[0]


def resolve_video_wallpaper_backend(state_path: Path) -> tuple[VideoWallpaperBackend, VideoWallpaperBackendStatus]:
    session_type = _session_type()
    desktop_tokens = _desktop_tokens()
    has_mpvpaper = shutil.which("mpvpaper") is not None
    has_mpv = shutil.which("mpv") is not None
    wlroots_compatible = _is_probably_wlroots(desktop_tokens, session_type)
    available = has_mpvpaper and has_mpv and wlroots_compatible
    if available:
        backend: VideoWallpaperBackend = MpvpaperWallpaperBackend(state_path)
        message = tr("Detection automatique: mpvpaper disponible pour wallpapers video sur Wayland/wlroots.")
    else:
        reasons: list[str] = []
        if not has_mpvpaper:
            reasons.append(tr("mpvpaper absent"))
        if not has_mpv:
            reasons.append(tr("mpv absent"))
        if not wlroots_compatible:
            reasons.append(tr("session non wlroots"))
        backend = NoopVideoWallpaperBackend(
            tr("Le support video requiert mpvpaper + mpv sur un compositeur wlroots compatible.")
        )
        message = tr(
            "Support video indisponible: {reasons}",
            reasons=", ".join(reasons or [tr("configuration inconnue")]),
        )
    return backend, VideoWallpaperBackendStatus(
        active_id=backend.backend_id,
        active_display_name=backend.display_name,
        available=available,
        session_type=session_type,
        desktop_environment=_desktop_environment_label(desktop_tokens),
        message=message,
    )
