from uuid import uuid4

from medivault.db.models import Medicine, Patient
from medivault.retrieval.graph import (
    _allergy_flags,
    _name_score,
    _score_candidate,
    _tokens,
)


def test_tokens_filters_short_words() -> None:
    assert _tokens("flu and bp high fever") == {"high", "fever"}


def test_score_candidate_overlaps_conditions() -> None:
    medicine = Medicine(
        id=uuid4(),
        generic_name="Paracetamol",
        indications="fever, mild pain",
        drug_class="Analgesic",
    )
    assert _score_candidate(medicine, {"fever", "diabetes"}) == 1
    assert _score_candidate(medicine, {"diabetes"}) == 0


def test_name_score_exact_alias_first() -> None:
    patient = Patient(id=uuid4(), full_name="Ali Khan", aliases=["Ali"])
    assert _name_score(patient, "ali") == 0
    assert _name_score(patient, "khan") == 1
    assert _name_score(patient, "zzz") == 2


def test_allergy_flags_match_contraindications() -> None:
    patient = Patient(id=uuid4(), full_name="A", allergies=["penicillin"])
    medicine = Medicine(
        id=uuid4(),
        generic_name="Amoxicillin",
        contraindications="Penicillin hypersensitivity",
    )
    flags = _allergy_flags(patient, [medicine])
    assert flags and "penicillin" in flags[0].lower()


def test_allergy_flags_no_match_when_clean() -> None:
    patient = Patient(id=uuid4(), full_name="A", allergies=["penicillin"])
    medicine = Medicine(id=uuid4(), generic_name="Paracetamol", warnings="none")
    assert _allergy_flags(patient, [medicine]) == []
