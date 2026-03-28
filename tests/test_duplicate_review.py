from __future__ import annotations

from pathlib import Path

from src.ui.dialogs.duplicate_review_dialog import DuplicateReviewDialog, DuplicateReviewGroup, duplicate_keep_score
from src.domain.enums import Orientation
from src.domain.models import Wallpaper


def _wallpaper(
    wallpaper_id: int,
    filename: str,
    *,
    width: int,
    height: int,
    rating: int = 0,
    views: int = 0,
    favorite: bool = False,
):
    return Wallpaper(
        id=wallpaper_id,
        path=Path(f"/tmp/{filename}"),
        filename=filename,
        extension=".jpg",
        folder_id=None,
        folder_path=None,
        width=width,
        height=height,
        orientation=Orientation.LANDSCAPE if width >= height else Orientation.PORTRAIT,
        aspect_ratio=(width / height) if height else None,
        size_bytes=1024,
        mtime=0,
        ctime=0,
        rating=rating,
        times_viewed=views,
        is_favorite=favorite,
    )


def test_duplicate_review_prefers_stronger_candidate(qt_app):
    weak = _wallpaper(1, "weak.jpg", width=1280, height=720, rating=1, views=0, favorite=False)
    strong = _wallpaper(2, "strong.jpg", width=3840, height=2160, rating=5, views=12, favorite=True)
    assert duplicate_keep_score(strong) > duplicate_keep_score(weak)

    dialog = DuplicateReviewDialog([DuplicateReviewGroup(sha256="abc", wallpapers=[weak, strong])])
    try:
        dialog._accept_with_selection()
        assert dialog.selected_ids_to_delete == [1]
    finally:
        dialog.close()
