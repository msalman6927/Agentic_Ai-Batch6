from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from medivault.db.base import Base, TimestampMixin


class InteractionSeverity(StrEnum):
    mild = "mild"
    moderate = "moderate"
    severe = "severe"
    contraindicated = "contraindicated"


class Medicine(Base, TimestampMixin):
    __tablename__ = "medicines"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    generic_name: Mapped[str] = mapped_column(String(256), index=True)
    brand_name: Mapped[str | None] = mapped_column(String(256), index=True)
    aliases: Mapped[list | None] = mapped_column(JSONB, default=list)
    drug_class: Mapped[str | None] = mapped_column(String(256), index=True)
    indications: Mapped[str | None] = mapped_column(Text)
    dosage: Mapped[str | None] = mapped_column(Text)
    route: Mapped[str | None] = mapped_column(String(128))
    contraindications: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[str | None] = mapped_column(Text)
    side_effects: Mapped[str | None] = mapped_column(Text)
    interactions_notes: Mapped[str | None] = mapped_column(Text)
    source_document_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
    )


class MedicineInteraction(Base, TimestampMixin):
    __tablename__ = "medicine_interactions"

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid4
    )
    medicine_a_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("medicines.id", ondelete="CASCADE"),
        index=True,
    )
    medicine_b_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("medicines.id", ondelete="CASCADE"),
        index=True,
    )
    severity: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
