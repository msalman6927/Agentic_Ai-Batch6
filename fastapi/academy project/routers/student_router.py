from fastapi import APIRouter, HTTPException, Path, status

from config.db import enrollments_db, students_db
from models.schemas import StudentCreate, StudentPatch, StudentResponse, StudentUpdate
from utils.helpers import delete_record, get_record, next_id


router = APIRouter(prefix="/students", tags=["students"])


def ensure_unique_email(email: str, excluded_id: int | None = None) -> None:
	for student_id, student in students_db.items():
		if student_id != excluded_id and student["email"] == email:
			raise HTTPException(
				status_code=status.HTTP_409_CONFLICT,
				detail="A student with this email already exists",
			)


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
def create_student(student: StudentCreate) -> dict:
	ensure_unique_email(student.email)
	student_id = next_id(students_db)
	students_db[student_id] = {"id": student_id, **student.dict()}
	return students_db[student_id]


@router.get("", response_model=list[StudentResponse])
def list_students() -> list[dict]:
	return list(students_db.values())


@router.get("/{student_id}", response_model=StudentResponse)
def get_student(student_id: int = Path(..., gt=0)) -> dict:
	return get_record(students_db, student_id, "Student")


@router.put("/{student_id}", response_model=StudentResponse)
def update_student(student: StudentUpdate, student_id: int = Path(..., gt=0)) -> dict:
	get_record(students_db, student_id, "Student")
	ensure_unique_email(student.email, student_id)
	students_db[student_id] = {"id": student_id, **student.dict()}
	return students_db[student_id]


@router.patch("/{student_id}", response_model=StudentResponse)
def patch_student(student: StudentPatch, student_id: int = Path(..., gt=0)) -> dict:
	current = get_record(students_db, student_id, "Student")
	updates = student.dict(exclude_unset=True)
	if "email" in updates:
		ensure_unique_email(updates["email"], student_id)
	current.update(updates)
	return current


@router.delete("/{student_id}", response_model=StudentResponse)
def delete_student(student_id: int = Path(..., gt=0)) -> dict:
	if any(enrollment["student_id"] == student_id for enrollment in enrollments_db.values()):
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail="Cannot delete a student with active enrollments",
		)
	return delete_record(students_db, student_id, "Student")
