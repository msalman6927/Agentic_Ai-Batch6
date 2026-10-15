from datetime import date
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Date, Float, ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from medivault.db.base import Base, TimestampMixin


class ConsultationStatus(StrEnum):
    draft = "draft"
    committed = "committed"
    cancelled = "cancelled"


class Consultation(Base, TimestampMixin):
    __tablename__ = "consultations"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    patient_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        index=True,
    )
    chief_complaint: Mapped[str | None] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    recommended: Mapped[list | None] = mapped_column(JSONB, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    follow_up_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
