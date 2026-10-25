"""Private local-disk storage for the initial VPS deployment."""

import asyncio
from pathlib import Path
import uuid

from shared.config.settings import settings


class LocalStorage:
    """Store files below a configured private root, never below public_html."""

    _photo_extensions = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    async def save_user_photo(
        self,
        user_id: uuid.UUID,
        content: bytes,
        content_type: str,
    ) -> str:
        extension = self._photo_extensions[content_type]
        filename = f"{uuid.uuid4().hex}{extension}"
        directory = self.root / "photos" / "users" / str(user_id)
        path = directory / filename

        def write() -> None:
            directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(write)
        return filename

    async def save_student_photo(
        self,
        school_id: uuid.UUID,
        student_id: uuid.UUID,
        content: bytes,
        content_type: str,
    ) -> str:
        extension = self._photo_extensions[content_type]
        filename = f"{uuid.uuid4().hex}{extension}"
        directory = self.root / "photos" / "students" / str(school_id) / str(student_id)
        path = directory / filename

        def write() -> None:
            directory.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)

        await asyncio.to_thread(write)
        return filename

    def user_photo_path(self, user_id: uuid.UUID, filename: str) -> Path:
        """Resolve a generated filename without allowing path traversal."""
        if Path(filename).name != filename:
            raise ValueError("Invalid filename")
        path = (self.root / "photos" / "users" / str(user_id) / filename).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage path")
        return path

    def student_photo_path(
        self,
        school_id: uuid.UUID,
        student_id: uuid.UUID,
        filename: str,
    ) -> Path:
        if Path(filename).name != filename:
            raise ValueError("Invalid filename")
        path = (
            self.root / "photos" / "students" / str(school_id) / str(student_id) / filename
        ).resolve()
        if self.root not in path.parents:
            raise ValueError("Invalid storage path")
        return path


local_storage = LocalStorage(settings.upload_dir)
