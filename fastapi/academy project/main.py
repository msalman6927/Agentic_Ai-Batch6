from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from middleware import RequestIDLoggingMiddleware, StaticSecurityHeadersMiddleware
from routers.auth_router import router as auth_router
from routers.course_router import router as course_router
from routers.enroll_router import router as enroll_router
from routers.file_router import router as file_router
from routers.student_router import router as student_router
from utils.auth import get_current_user
from utils.files import STATIC_DIR, ensure_static_dir


app = FastAPI(title="Academy API", version="1.0.0")

app.add_middleware(RequestIDLoggingMiddleware)
app.add_middleware(StaticSecurityHeadersMiddleware)

_protected = [Depends(get_current_user)]

app.include_router(auth_router)
app.include_router(student_router, dependencies=_protected)
app.include_router(course_router, dependencies=_protected)
app.include_router(enroll_router, dependencies=_protected)
app.include_router(file_router)

ensure_static_dir()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", tags=["health"])
def health_check() -> dict[str, str]:
	return {"message": "Academy API is running"}
