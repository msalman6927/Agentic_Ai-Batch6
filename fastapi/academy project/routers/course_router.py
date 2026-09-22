from fastapi import APIRouter, HTTPException, Path, status

from config.db import courses_db, enrollments_db
from models.schemas import CourseCreate, CoursePatch, CourseResponse, CourseUpdate
from utils.helpers import delete_record, get_record, next_id


router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
def create_course(course: CourseCreate) -> dict:
	course_id = next_id(courses_db)
	courses_db[course_id] = {"id": course_id, **course.dict()}
	return courses_db[course_id]


@router.get("", response_model=list[CourseResponse])
def list_courses() -> list[dict]:
	return list(courses_db.values())


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: int = Path(..., gt=0)) -> dict:
	return get_record(courses_db, course_id, "Course")


@router.put("/{course_id}", response_model=CourseResponse)
def update_course(course: CourseUpdate, course_id: int = Path(..., gt=0)) -> dict:
	get_record(courses_db, course_id, "Course")
	courses_db[course_id] = {"id": course_id, **course.dict()}
	return courses_db[course_id]


@router.patch("/{course_id}", response_model=CourseResponse)
def patch_course(course: CoursePatch, course_id: int = Path(..., gt=0)) -> dict:
	current = get_record(courses_db, course_id, "Course")
	current.update(course.dict(exclude_unset=True))
	return current


@router.delete("/{course_id}", response_model=CourseResponse)
def delete_course(course_id: int = Path(..., gt=0)) -> dict:
	if any(enrollment["course_id"] == course_id for enrollment in enrollments_db.values()):
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Cannot delete a course with active enrollments",
		)
	return delete_record(courses_db, course_id, "Course")
