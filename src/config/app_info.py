from __future__ import annotations

from importlib.resources import files


APP_NAME = "Nyini"
APP_ORGANIZATION = "TheOnlyDuckxx"
APP_DESKTOP_FILE = "nyini"


def app_icon_path() -> str:
    return str(files("src.assets.icons").joinpath("nyini.png"))


def stylesheet_text(theme_name: str) -> str:
    return files("src.assets.styles").joinpath(f"app_{theme_name}.qss").read_text(encoding="utf-8")
