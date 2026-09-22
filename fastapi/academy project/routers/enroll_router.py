from fastapi import APIRouter, HTTPException, Path, status

from config.db import courses_db, enrollments_db, students_db
from models.schemas import (
	EnrollmentCreate,
	EnrollmentPatch,
	EnrollmentResponse,
	EnrollmentUpdate,
)
from utils.helpers import delete_record, get_record, next_id


router = APIRouter(prefix="/enrollments", tags=["enrollments"])


def validate_relationship(student_id: int, course_id: int) -> None:
	get_record(students_db, student_id, "Student")
	get_record(courses_db, course_id, "Course")


def ensure_unique_enrollment(
	student_id: int,
	course_id: int,
	excluded_id: int | None = None,
) -> None:
	for enrollment_id, enrollment in enrollments_db.items():
		if enrollment_id != excluded_id and (
			enrollment["student_id"] == student_id
			and enrollment["course_id"] == course_id
		):
			raise HTTPException(
				status_code=status.HTTP_409_CONFLICT,
				detail="This student is already enrolled in this course",
			)


@router.post("", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
def create_enrollment(enrollment: EnrollmentCreate) -> dict:
	validate_relationship(enrollment.student_id, enrollment.course_id)
	ensure_unique_enrollment(enrollment.student_id, enrollment.course_id)
	enrollment_id = next_id(enrollments_db)
	enrollments_db[enrollment_id] = {"id": enrollment_id, **enrollment.dict()}
	return enrollments_db[enrollment_id]


@router.get("", response_model=list[EnrollmentResponse])
def list_enrollments() -> list[dict]:
	return list(enrollments_db.values())


@router.get("/{enrollment_id}", response_model=EnrollmentResponse)
def get_enrollment(enrollment_id: int = Path(..., gt=0)) -> dict:
	return get_record(enrollments_db, enrollment_id, "Enrollment")


@router.put("/{enrollment_id}", response_model=EnrollmentResponse)
def update_enrollment(
	enrollment: EnrollmentUpdate,
	enrollment_id: int = Path(..., gt=0),
) -> dict:
	get_record(enrollments_db, enrollment_id, "Enrollment")
	validate_relationship(enrollment.student_id, enrollment.course_id)
	ensure_unique_enrollment(enrollment.student_id, enrollment.course_id, enrollment_id)
	enrollments_db[enrollment_id] = {"id": enrollment_id, **enrollment.dict()}
	return enrollments_db[enrollment_id]


@router.patch("/{enrollment_id}", response_model=EnrollmentResponse)
def patch_enrollment(
	enrollment: EnrollmentPatch,
	enrollment_id: int = Path(..., gt=0),
) -> dict:
	current = get_record(enrollments_db, enrollment_id, "Enrollment")
	updates = enrollment.dict(exclude_unset=True)
	candidate_student_id = updates.get("student_id", current["student_id"])
	candidate_course_id = updates.get("course_id", current["course_id"])
	validate_relationship(candidate_student_id, candidate_course_id)
	ensure_unique_enrollment(candidate_student_id, candidate_course_id, enrollment_id)
	current.update(updates)
	return current


@router.delete("/{enrollment_id}", response_model=EnrollmentResponse)
def delete_enrollment(enrollment_id: int = Path(..., gt=0)) -> dict:
	return delete_record(enrollments_db, enrollment_id, "Enrollment")
