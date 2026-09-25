import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi import HTTPException, UploadFile, status


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
ALLOWED_EXTENSIONS = {
	".jpg",
	".jpeg",
	".png",
	".gif",
	".webp",
	".svg",
	".pdf",
	".txt",
	".csv",
	".json",
}
MAX_FILE_SIZE = 10 * 1024 * 1024
_CHUNK_SIZE = 1024 * 1024
_FORBIDDEN_CHARS = set('<>:"|?*') | {chr(i) for i in range(32)}


def ensure_static_dir() -> None:
	STATIC_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_filename(filename: str) -> str:
	name = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
	if not name or name in {".", ".."}:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Invalid filename",
		)
	if any(char in _FORBIDDEN_CHARS for char in name):
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Filename contains invalid characters",
		)
	return name


def ensure_allowed_extension(filename: str) -> None:
	extension = Path(filename).suffix.lower()
	if extension not in ALLOWED_EXTENSIONS:
		allowed = ", ".join(sorted(ext.lstrip(".") for ext in ALLOWED_EXTENSIONS))
		raise HTTPException(
			status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
			detail=f"File type not allowed. Allowed types: {allowed}",
		)


def _is_inside_static(path: Path) -> bool:
	return path.resolve().is_relative_to(STATIC_DIR.resolve())


def unique_path(filename: str) -> Path:
	target = STATIC_DIR / filename
	if not target.exists():
		return target
	stem = Path(filename).stem
	suffix = Path(filename).suffix
	counter = 1
	while True:
		candidate = STATIC_DIR / f"{stem}({counter}){suffix}"
		if not candidate.exists():
			return candidate
		counter += 1


async def save_upload(file: UploadFile) -> tuple[str, int]:
	if not file.filename:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Missing filename",
		)
	name = sanitize_filename(file.filename)
	ensure_allowed_extension(name)
	ensure_static_dir()

	temp_path = STATIC_DIR / f".uploading_{uuid.uuid4().hex}"
	total = 0
	try:
		with temp_path.open("wb") as destination:
			while chunk := await file.read(_CHUNK_SIZE):
				total += len(chunk)
				if total > MAX_FILE_SIZE:
					raise HTTPException(
						status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
						detail=f"File exceeds the {MAX_FILE_SIZE // (1024 * 1024)} MB limit",
					)
				destination.write(chunk)
		if total == 0:
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="Empty file is not allowed",
			)
		final_path = unique_path(name)
		if not _is_inside_static(final_path):
			raise HTTPException(
				status_code=status.HTTP_400_BAD_REQUEST,
				detail="Invalid filename",
			)
		temp_path.replace(final_path)
		return final_path.name, total
	finally:
		if temp_path.exists():
			temp_path.unlink()


def list_files() -> list[dict[str, Any]]:
	ensure_static_dir()
	entries: list[dict[str, Any]] = []
	for path in sorted(STATIC_DIR.iterdir()):
		if path.is_file() and not path.name.startswith("."):
			entries.append({"filename": path.name, "size_bytes": path.stat().st_size})
	return entries


def delete_file(filename: str) -> str:
	name = sanitize_filename(filename)
	ensure_static_dir()
	target = STATIC_DIR / name
	if not target.is_file() or not _is_inside_static(target):
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="File not found",
		)
	target.unlink()
	return name


def file_url(base_url: str, filename: str) -> str:
	return f"{base_url}static/{quote(filename)}"
