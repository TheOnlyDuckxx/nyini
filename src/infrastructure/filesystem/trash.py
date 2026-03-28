from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from urllib.parse import quote, unquote

from src.domain.models import TrashRecord


class TrashManager:
    def __init__(self, files_dir: Path, info_dir: Path) -> None:
        self.files_dir = files_dir
        self.info_dir = info_dir
        self.files_dir.mkdir(parents=True, exist_ok=True)
        self.info_dir.mkdir(parents=True, exist_ok=True)

    def _unique_name(self, name: str) -> str:
        candidate = name
        stem = Path(name).stem
        suffix = Path(name).suffix
        counter = 1
        while (self.files_dir / candidate).exists() or (self.info_dir / f"{candidate}.trashinfo").exists():
            candidate = f"{stem} ({counter}){suffix}"
            counter += 1
        return candidate

    def trash(self, path: Path) -> TrashRecord:
        if not path.exists():
            raise FileNotFoundError(path)
        deleted_at = datetime.now().replace(microsecond=0).isoformat()
        unique_name = self._unique_name(path.name)
        trashed_path = self.files_dir / unique_name
        info_path = self.info_dir / f"{unique_name}.trashinfo"
        shutil.move(str(path), str(trashed_path))
        info_path.write_text(
            "\n".join(
                [
                    "[Trash Info]",
                    f"Path={quote(str(path))}",
                    f"DeletionDate={deleted_at}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return TrashRecord(
            original_path=path,
            trashed_path=trashed_path,
            info_path=info_path,
            deletion_date=deleted_at,
        )

    def restore(self, record: TrashRecord) -> Path:
        if not record.trashed_path.exists():
            raise FileNotFoundError(record.trashed_path)
        original_path = record.original_path
        restored_path = original_path
        if restored_path.exists():
            stem = original_path.stem
            suffix = original_path.suffix
            counter = 1
            while restored_path.exists():
                restored_path = original_path.with_name(f"{stem} ({counter}){suffix}")
                counter += 1
        restored_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(record.trashed_path), str(restored_path))
        if record.info_path.exists():
            record.info_path.unlink()
        return restored_path

    def read_info(self, info_path: Path) -> TrashRecord:
        raw_path = ""
        deleted_at = ""
        for line in info_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("Path="):
                raw_path = unquote(line.split("=", 1)[1])
            if line.startswith("DeletionDate="):
                deleted_at = line.split("=", 1)[1]
        trashed_path = self.files_dir / info_path.name.removesuffix(".trashinfo")
        return TrashRecord(
            original_path=Path(raw_path),
            trashed_path=trashed_path,
            info_path=info_path,
            deletion_date=deleted_at,
        )
