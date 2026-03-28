from __future__ import annotations

from pathlib import Path
import shutil


class FileMover:
    def unique_destination(self, destination: Path) -> Path:
        if not destination.exists():
            return destination
        stem = destination.stem
        suffix = destination.suffix
        counter = 1
        while True:
            candidate = destination.with_name(f"{stem} ({counter}){suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def move(
        self,
        source: Path,
        destination: Path,
        *,
        ensure_unique: bool = True,
        overwrite: bool = False,
    ) -> Path:
        if not source.exists():
            raise FileNotFoundError(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        final_destination = self.unique_destination(destination) if ensure_unique else destination
        if source.resolve() == final_destination.resolve():
            return final_destination
        if overwrite and final_destination.exists():
            final_destination.unlink()
        shutil.move(str(source), str(final_destination))
        return final_destination
