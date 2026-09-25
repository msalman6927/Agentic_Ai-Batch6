from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from utils.auth import get_current_user
from utils.files import delete_file, file_url, list_files, save_upload


router = APIRouter(tags=["files"])


@router.post(
	"/upload",
	status_code=status.HTTP_201_CREATED,
	dependencies=[Depends(get_current_user)],
)
async def upload_file(request: Request, file: UploadFile = File(...)) -> dict:
	filename, size_bytes = await save_upload(file)
	return {
		"filename": filename,
		"url": file_url(str(request.base_url), filename),
		"size_bytes": size_bytes,
	}


@router.get("/files")
def list_uploaded_files(request: Request) -> dict:
	base = str(request.base_url)
	files = [
		{"filename": entry["filename"], "url": file_url(base, entry["filename"])}
		for entry in list_files()
	]
	return {"count": len(files), "files": files}


@router.delete(
	"/files/{filename}",
	dependencies=[Depends(get_current_user)],
)
def remove_uploaded_file(filename: str) -> dict:
	return {"deleted": delete_file(filename)}
