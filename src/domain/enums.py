from __future__ import annotations

from enum import Enum


class Orientation(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    SQUARE = "square"
    UNKNOWN = "unknown"


class MediaKind(str, Enum):
    IMAGE = "image"
    VIDEO = "video"


class SortField(str, Enum):
    NAME = "name"
    MTIME = "mtime"
    SIZE = "size"
    ORIENTATION = "orientation"
    FAVORITE = "favorite"
    RATING = "rating"
    VIEWS = "views"
    BRIGHTNESS = "brightness"


class ThemeMode(str, Enum):
    AUTO = "auto"
    LIGHT = "light"
    DARK = "dark"


class AppLanguage(str, Enum):
    FR = "fr"
    EN = "en"


class WallpaperSourceKind(str, Enum):
    LOCAL = "local"
    WALLHAVEN = "wallhaven"
    MANUAL_IMPORT = "manual_import"
    GOWALL_GENERATED = "gowall_generated"
    DERIVED_EDIT = "derived_edit"


class SmartCollection(str, Enum):
    FAVORITES = "favorites"
    VIDEOS = "videos"
    PORTRAITS = "portraits"
    LANDSCAPES = "landscapes"
    SQUARES = "squares"
    NEVER_VIEWED = "never_viewed"
    TOP_RATED = "top_rated"
    DUPLICATES = "duplicates"
    DARK = "dark"
    ANIME = "anime"
    MINIMAL = "minimal"
    UNTAGGED = "untagged"
    RECENT = "recent"
    INBOX = "inbox"
