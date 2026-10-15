import contextlib
import re
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from medivault.db.models import Consultation, Medicine, MedicineInteraction, Patient
from medivault.dependencies import get_session_factory
from medivault.utils.errors import NotFoundError

_MAX_CANDIDATES = 12
_MAX_PAST_CONSULTATIONS = 20
_WORD_RE = re.compile(r"[a-zA-Z]{4,}")


@dataclass
class GraphContext:
    patient_id: UUID
    patient_name: str
    conditions: list[str] = field(default_factory=list)
    allergies: list[str] = field(default_factory=list)
    candidate_medicines: list[dict] = field(default_factory=list)
    past_medicines: list[dict] = field(default_factory=list)
    interactions: list[dict] = field(default_factory=list)
    allergy_flags: list[str] = field(default_factory=list)

    def to_payload(self) -> dict:
        return {
            "patient_id": str(self.patient_id),
            "patient_name": self.patient_name,
            "conditions": self.conditions,
            "allergies": self.allergies,
            "candidate_medicines": self.candidate_medicines,
            "past_medicines": self.past_medicines,
            "interactions": self.interactions,
            "allergy_flags": self.allergy_flags,
        }


def _tokens(text: str | None) -> set[str]:
    return {token.lower() for token in _WORD_RE.findall(text or "")}


def _name_score(patient: Patient, needle: str) -> int:
    names = [patient.full_name.lower()]
    names.extend(alias.lower() for alias in (patient.aliases or []))
    if needle in names:
        return 0
    if any(needle in name for name in names):
        return 1
    return 2


async def find_patients_by_name(
    session: AsyncSession, name: str, *, limit: int = 10
) -> list[Patient]:
    """Alias-aware patient resolution (exact full_name/alias first, then fuzzy)."""
    needle = name.strip().lower()
    if not needle:
        return []
    candidates = await session.scalars(
        select(Patient)
        .where(
            or_(
                Patient.full_name.ilike(f"%{needle}%"),
                cast(Patient.aliases, Text).ilike(f"%{needle}%"),
            )
        )
        .limit(50)
    )
    patients = sorted(candidates, key=lambda p: _name_score(p, needle))
    return patients[:limit]


async def _load_interactions(
    session: AsyncSession, medicine_ids: list[UUID]
) -> list[dict]:
    if not medicine_ids:
        return []
    rows = await session.scalars(
        select(MedicineInteraction).where(
            MedicineInteraction.medicine_a_id.in_(medicine_ids)
            | MedicineInteraction.medicine_b_id.in_(medicine_ids)
        )
    )
    id_set = set(medicine_ids)
    names = {}
    results: list[dict] = []
    for interaction in rows:
        for mid in (interaction.medicine_a_id, interaction.medicine_b_id):
            if mid not in names and mid in id_set:
                medicine = await session.get(Medicine, mid)
                names[mid] = medicine.generic_name if medicine else str(mid)
        results.append(
            {
                "medicine_a": names.get(
                    interaction.medicine_a_id, str(interaction.medicine_a_id)
                ),
                "medicine_b": names.get(
                    interaction.medicine_b_id, str(interaction.medicine_b_id)
                ),
                "severity": interaction.severity,
                "description": interaction.description,
            }
        )
    return results


def _score_candidate(medicine: Medicine, condition_tokens: set[str]) -> int:
    haystack = " ".join(
        [
            medicine.generic_name or "",
            medicine.brand_name or "",
            medicine.drug_class or "",
            medicine.indications or "",
        ]
    ).lower()
    return len(condition_tokens & _tokens(haystack))


def _allergy_flags(patient: Patient, medicines: list[Medicine]) -> list[str]:
    flags: list[str] = []
    allergy_tokens: set[str] = set()
    for allergy in patient.allergies or []:
        allergy_tokens |= _tokens(allergy)
    if not allergy_tokens:
        return flags
    for medicine in medicines:
        text = " ".join(
            [
                medicine.contraindications or "",
                medicine.warnings or "",
                medicine.side_effects or "",
            ]
        ).lower()
        hits = allergy_tokens & _tokens(text)
        if hits:
            flags.append(
                f"{medicine.generic_name}: text mentions {', '.join(sorted(hits))}"
                " — verify against patient allergy list"
            )
    return flags


async def expand_patient_graph(
    patient_id: UUID, session: AsyncSession | None = None
) -> GraphContext:
    """Patient -> conditions -> candidate medicines -> interactions/allergy flags."""
    if session is None:
        factory = get_session_factory()
        async with factory() as own_session:
            return await expand_patient_graph(patient_id, own_session)

    patient = await session.get(Patient, patient_id)
    if patient is None:
        raise NotFoundError(f"patient {patient_id} not found")

    context = GraphContext(
        patient_id=patient.id,
        patient_name=patient.full_name,
        conditions=list(patient.conditions or []),
        allergies=list(patient.allergies or []),
    )

    consultations = list(
        await session.scalars(
            select(Consultation)
            .where(
                Consultation.patient_id == patient_id,
                Consultation.status == "committed",
            )
            .order_by(Consultation.created_at.desc())
            .limit(_MAX_PAST_CONSULTATIONS)
        )
    )
    past_ids: list[UUID] = []
    for consultation in consultations:
        for item in consultation.recommended or []:
            name = item.get("name") or item.get("medicine_name") or ""
            context.past_medicines.append(
                {
                    "name": name,
                    "dose": item.get("dose"),
                    "frequency": item.get("frequency"),
                    "duration": item.get("duration"),
                    "diagnosis": consultation.diagnosis,
                    "date": consultation.created_at.isoformat()
                    if consultation.created_at
                    else None,
                }
            )
            if item.get("medicine_id"):
                with contextlib.suppress(ValueError):
                    past_ids.append(UUID(str(item["medicine_id"])))

    condition_tokens: set[str] = set()
    for condition in context.conditions:
        condition_tokens |= _tokens(condition)

    candidates: list[tuple[int, Medicine]] = []
    if condition_tokens:
        medicines = await session.scalars(select(Medicine).limit(500))
        for medicine in medicines:
            score = _score_candidate(medicine, condition_tokens)
            if score > 0:
                candidates.append((score, medicine))
    candidates.sort(key=lambda pair: pair[0], reverse=True)

    involved_ids = list(past_ids)
    top_medicines: list[Medicine] = []
    for _, medicine in candidates[:_MAX_CANDIDATES]:
        involved_ids.append(medicine.id)
        top_medicines.append(medicine)
        context.candidate_medicines.append(
            {
                "id": str(medicine.id),
                "generic_name": medicine.generic_name,
                "brand_name": medicine.brand_name,
                "drug_class": medicine.drug_class,
                "dosage": medicine.dosage,
                "indications": medicine.indications,
                "contraindications": medicine.contraindications,
            }
        )
    context.interactions = await _load_interactions(session, involved_ids)
    past_medicine_rows = [await session.get(Medicine, mid) for mid in past_ids]
    all_rows = top_medicines + [m for m in past_medicine_rows if m is not None]
    context.allergy_flags = _allergy_flags(patient, all_rows)
    return context


async def check_interactions_for_names(names: list[str]) -> list[dict]:
    factory = get_session_factory()
    async with factory() as session:
        medicines: list[Medicine] = []
        for name in names:
            pattern = f"%{name.strip()}%"
            row = (
                await session.scalars(
                    select(Medicine)
                    .where(
                        or_(
                            Medicine.generic_name.ilike(pattern),
                            func.coalesce(Medicine.brand_name, "").ilike(pattern),
                        )
                    )
                    .limit(1)
                )
            ).first()
            if row is not None:
                medicines.append(row)
        interactions = await _load_interactions(session, [m.id for m in medicines])
        return [
            {
                "requested": names,
                "resolved": [m.generic_name for m in medicines],
                "interactions": interactions,
            }
        ]
