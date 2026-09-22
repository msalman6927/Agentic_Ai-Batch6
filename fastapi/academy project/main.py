from fastapi import FastAPI

from routers.course_router import router as course_router
from routers.enroll_router import router as enroll_router
from routers.student_router import router as student_router


app = FastAPI(title="Academy API", version="1.0.0")

app.include_router(student_router)
app.include_router(course_router)
app.include_router(enroll_router)


@app.get("/", tags=["health"])
def health_check() -> dict[str, str]:
	return {"message": "Academy API is running"}
