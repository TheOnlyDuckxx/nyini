from __future__ import annotations

import hashlib
from pathlib import Path
import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageOps

from src.domain.enums import MediaKind
from src.infrastructure.imaging.metadata import detect_media_kind


class ThumbnailManager:
    def __init__(self, thumbnails_dir: Path, size: int = 256) -> None:
        self.thumbnails_dir = thumbnails_dir
        self.size = size
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, source_path: Path, *, mtime: float, size_bytes: int) -> str:
        payload = f"{source_path}|{mtime}|{size_bytes}|{self.size}".encode("utf-8")
        return hashlib.sha1(payload, usedforsecurity=False).hexdigest()

    def thumbnail_path_for(self, source_path: Path, *, mtime: float, size_bytes: int) -> Path:
        return self.thumbnails_dir / f"{self._cache_key(source_path, mtime=mtime, size_bytes=size_bytes)}.png"

    def ensure_thumbnail(self, source_path: Path, *, mtime: float, size_bytes: int) -> Path:
        destination = self.thumbnail_path_for(source_path, mtime=mtime, size_bytes=size_bytes)
        if destination.exists():
            return destination

        temp_destination = destination.with_suffix(".tmp")
        if detect_media_kind(source_path) is MediaKind.VIDEO:
            self._generate_video_thumbnail(source_path, temp_destination)
        else:
            self._generate_image_thumbnail(source_path, temp_destination)
        os.replace(temp_destination, destination)
        return destination

    def _generate_image_thumbnail(self, source_path: Path, destination: Path) -> None:
        with Image.open(source_path) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((self.size, self.size))
            canvas = Image.new("RGBA", (self.size, self.size), (24, 24, 28, 255))
            offset = ((self.size - image.width) // 2, (self.size - image.height) // 2)
            canvas.paste(image.convert("RGBA"), offset)
            canvas.save(destination, format="PNG")

    def _generate_video_thumbnail(self, source_path: Path, destination: Path) -> None:
        frame_path = destination.with_suffix(".frame.png")
        try:
            if shutil.which("ffmpeg") is not None:
                result = subprocess.run(
                    [
                        "ffmpeg",
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-ss",
                        "0",
                        "-i",
                        str(source_path),
                        "-frames:v",
                        "1",
                        str(frame_path),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and frame_path.exists():
                    with Image.open(frame_path) as frame:
                        frame = frame.convert("RGBA")
                        frame.thumbnail((self.size, self.size))
                        canvas = Image.new("RGBA", (self.size, self.size), (14, 18, 28, 255))
                        offset = ((self.size - frame.width) // 2, (self.size - frame.height) // 2)
                        canvas.paste(frame, offset)
                        self._draw_video_badge(canvas)
                        canvas.save(destination, format="PNG")
                        return
        finally:
            if frame_path.exists():
                frame_path.unlink()
        placeholder = Image.new("RGBA", (self.size, self.size), (14, 18, 28, 255))
        draw = ImageDraw.Draw(placeholder)
        inset = max(18, self.size // 10)
        draw.rounded_rectangle(
            (inset, inset, self.size - inset, self.size - inset),
            radius=18,
            outline=(121, 134, 203, 255),
            width=3,
            fill=(28, 36, 52, 255),
        )
        triangle = [
            (self.size * 0.42, self.size * 0.34),
            (self.size * 0.42, self.size * 0.66),
            (self.size * 0.68, self.size * 0.50),
        ]
        draw.polygon(triangle, fill=(230, 235, 245, 255))
        draw.text((self.size * 0.27, self.size * 0.78), "VIDEO", fill=(180, 188, 208, 255))
        placeholder.save(destination, format="PNG")

    def _draw_video_badge(self, canvas: Image.Image) -> None:
        draw = ImageDraw.Draw(canvas)
        height = max(28, self.size // 8)
        draw.rounded_rectangle(
            (10, self.size - height - 10, 88, self.size - 10),
            radius=10,
            fill=(0, 0, 0, 190),
        )
        draw.text((24, self.size - height - 1), "VIDEO", fill=(235, 240, 248, 255))
