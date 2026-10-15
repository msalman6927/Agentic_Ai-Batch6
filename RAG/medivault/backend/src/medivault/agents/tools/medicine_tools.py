import json

from langchain_core.tools import tool

from medivault.retrieval.graph import check_interactions_for_names
from medivault.retrieval.hybrid import hybrid_search


@tool
async def search_medicines(query: str, k: int = 5) -> str:
    """Hybrid search over the uploaded medicine catalog (dense + keyword).

    Use for: finding medicines by name, indication, class, dosage questions.
    """
    hits = await hybrid_search(query, doc_type="medicine", k=min(k, 10))
    if not hits:
        return "No matching medicines found in the vault."
    lines = []
    for index, hit in enumerate(hits, start=1):
        lines.append(
            f"{index}. score={hit.score:.3f} dense={hit.dense_rank} "
            f"sparse={hit.sparse_rank}\n{hit.snippet}"
        )
    return "\n\n".join(lines)


@tool
async def search_documents(query: str, k: int = 5, doc_type: str = "") -> str:
    """Search raw PDF chunks (medicines and/or patient documents).

    doc_type: 'medicine', 'patient', or '' for both.
    """
    kind = doc_type.strip() or None
    if kind not in (None, "medicine", "patient"):
        return "doc_type must be 'medicine', 'patient' or empty"
    hits = await hybrid_search(query, doc_type=kind, k=min(k, 10))
    if not hits:
        return "No matching documents found."
    lines = []
    for index, hit in enumerate(hits, start=1):
        lines.append(
            f"{index}. ({hit.doc_type or 'doc'}) score={hit.score:.3f}\n{hit.snippet}"
        )
    return "\n\n".join(lines)


@tool
async def check_interactions(medicine_names: list[str]) -> str:
    """Check drug-drug interactions and resolution for a list of medicine names."""
    if not medicine_names:
        return "Provide at least one medicine name."
    results = await check_interactions_for_names(medicine_names)
    payload = results[0] if results else {}
    interactions = payload.get("interactions", [])
    if not interactions:
        return json.dumps(
            {
                "resolved": payload.get("resolved", []),
                "interactions": [],
                "note": "No known interactions found in vault for resolved medicines.",
            },
            ensure_ascii=False,
        )
    return json.dumps(payload, ensure_ascii=False, indent=2)
