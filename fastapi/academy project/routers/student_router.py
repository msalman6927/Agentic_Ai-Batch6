from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config.db import get_db
from models.schemas import StudentCreate, StudentPatch, StudentResponse, StudentUpdate
from models.tables import Enrollment, Student
from utils.auth import hash_password
from utils.helpers import ensure_email_available, get_or_404


router = APIRouter(prefix="/students", tags=["students"])

_EMAIL_CONFLICT = "A student with this email already exists"
_ENROLLMENT_CONFLICT = "Cannot delete a student with active enrollments"


async def ensure_unique_email(
	db: AsyncSession,
	email: str,
	excluded_id: int | None = None,
) -> None:
	await ensure_email_available(db, Student, email, _EMAIL_CONFLICT, excluded_id)


async def has_enrollments(db: AsyncSession, student_id: int) -> bool:
	result = await db.execute(
		select(Enrollment.id).where(Enrollment.student_id == student_id).limit(1)
	)
	return result.scalar_one_or_none() is not None


@router.post("", response_model=StudentResponse, status_code=status.HTTP_201_CREATED)
async def create_student(
	student: StudentCreate,
	db: AsyncSession = Depends(get_db),
) -> Student:
	await ensure_unique_email(db, student.email)
	hashed_password = await run_in_threadpool(hash_password, student.password)
	record = Student(
		name=student.name,
		email=student.email,
		password=hashed_password,
	)
	db.add(record)
	await db.commit()
	await db.refresh(record)
	return record


@router.get("", response_model=list[StudentResponse])
async def list_students(db: AsyncSession = Depends(get_db)) -> list[Student]:
	result = await db.execute(select(Student).order_by(Student.id))
	return list(result.scalars().all())


@router.get("/{student_id}", response_model=StudentResponse)
async def get_student(
	student_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Student:
	return await get_or_404(db, Student, student_id, "Student")


@router.put("/{student_id}", response_model=StudentResponse)
async def update_student(
	student: StudentUpdate,
	student_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Student:
	record = await get_or_404(db, Student, student_id, "Student")
	await ensure_unique_email(db, student.email, student_id)
	record.name = student.name
	record.email = student.email
	record.password = await run_in_threadpool(hash_password, student.password)
	await db.commit()
	return record


@router.patch("/{student_id}", response_model=StudentResponse)
async def patch_student(
	student: StudentPatch,
	student_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Student:
	record = await get_or_404(db, Student, student_id, "Student")
	updates = student.model_dump(exclude_unset=True)
	if "email" in updates:
		await ensure_unique_email(db, updates["email"], student_id)
	if "password" in updates:
		updates["password"] = await run_in_threadpool(hash_password, updates["password"])
	for field, value in updates.items():
		setattr(record, field, value)
	await db.commit()
	return record


@router.delete("/{student_id}", response_model=StudentResponse)
async def delete_student(
	student_id: int = Path(..., gt=0),
	db: AsyncSession = Depends(get_db),
) -> Student:
	record = await get_or_404(db, Student, student_id, "Student")
	if await has_enrollments(db, student_id):
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=_ENROLLMENT_CONFLICT,
		)
	await db.delete(record)
	try:
		await db.commit()
	except IntegrityError:
		await db.rollback()
		raise HTTPException(
			status_code=status.HTTP_409_CONFLICT,
			detail=_ENROLLMENT_CONFLICT,
		)
	return record
