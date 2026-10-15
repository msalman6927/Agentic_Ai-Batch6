# MediVault Backend

Agentic clinical RAG for doctors: hybrid retrieval (Chroma dense + Postgres FTS),
Postgres-as-graph, LangGraph agent with confirm-before-save consultations, citations +
confidence scoring, sales CSV analytics. Product context: see `../context.md`.

## Run

```bash
# from repo root (never bare uv sync inside the member)
uv sync --all-packages --all-groups

uv run ruff format . && uv run ruff check . --fix
uv run mypy src
uv run pytest -q                     # unit only (default: no live services needed)
uv run pytest -q -m integration      # + live Neon/Chroma/Gemini (~5 min)
uv run pytest -q -m eval             # + LLM smoke eval (~4 min)
uv run alembic upgrade head
uv run uvicorn medivault.main:app --reload   # GET /health
```

## Env

`RAG/medivault/.env` (gitignored):

```
database_url=postgresql://...      # Neon DSN (bare, driver added in code)
gemini_api_key=...
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness + DB ping |
| POST | `/documents` | upload medicine/patient PDF (multipart `file` + `doc_type`) |
| GET | `/documents` · `GET /documents/{id}` · `DELETE /documents/{id}` | manage PDFs |
| GET/POST/PUT/DELETE | `/medicines…` | medicine catalog CRUD |
| GET/POST/PUT/DELETE | `/patients…` | patient records CRUD |
| GET | `/patients/{id}/consultations` | committed history for a patient |
| POST | `/consultations` | create + commit manually |
| GET | `/consultations` · `GET /consultations/{id}` | list/filter, fetch one |
| POST | `/consultations/confirm` · `/consultations/cancel` | confirm-before-save flow |
| POST | `/sales/upload` | CSV upload (`sale_date,item_name,quantity,unit_price`) |
| GET | `/sales` · `/sales/summary` · `DELETE /sales/uploads/{id}` | query + aggregates |
| POST | `/chat` | **SSE** agent stream |
| GET | `/conversations` · `GET /conversations/{id}/messages` | chat history |

## SSE contract (`POST /chat`)

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the dosage of Paracetamol?","patient_id":null}'
```

Events, in order: `meta`, `sources`, `tool_call`/`tool_result` (loops), `token`*
(final answer), `confidence`, optional `confirm_required`, `done`. Errors arrive as
`event: error` mid-stream or `{"error":{"code","detail"}}` on non-2xx.

## Agent tools

`search_medicines` · `search_documents` · `check_interactions` · `search_patients` ·
`get_patient_record` · `get_patient_history` · `search_memory` ·
`record_consultation` (write → draft + `confirm_required`) · `get_sales_summary`
