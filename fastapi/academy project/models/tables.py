from sqlalchemy import ForeignKey, Identity, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)


class Course(Base):
	__tablename__ = "courses"

	id: Mapped[int] = mapped_column(Identity(), primary_key=True)
	title: Mapped[str] = mapped_column(String(150), nullable=False)
	description: Mapped[str] = mapped_column(String(2000), nullable=False)
	instructor: Mapped[str] = mapped_column(String(100), nullable=False)
	outline: Mapped[str] = mapped_column(String(2000), nullable=True)


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_enrollments_student_course"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
