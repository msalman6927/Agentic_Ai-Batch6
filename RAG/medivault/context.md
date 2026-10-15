# MediVault — Project Context

> Living document. Update after **every** session/phase so any terminal can resume with zero context loss.

---

## 1. Product one-liner

**MediVault** is a doctor-facing clinical RAG agent. The doctor uploads medicine catalogs and
patient records (PDFs) + daily sales (CSV). A LangGraph agent answers clinical questions
("which medicine should I recommend for patient X?") using **hybrid retrieval** (Chroma dense +
Postgres FTS) + a **Postgres graph layer**, cites every claim with a **confidence score**, and
**permanently saves consultations** (after doctor confirmation) so future questions about the
same patient recall prior visits.

## 2. Persona / product rules

- The agent is a **medical assistant persona**: always replies, stays strictly on clinical
  topics, redirects non-medical chatter back to medicine/patients/sales.
- When the vault has no answer it still replies in persona (general medical guidance), but the
  answer is flagged **low-confidence, not from vault** and carries **no citations**.
- Answers must be built from vault sources whenever possible, each claim cited `[n]`.
- Write tools never auto-commit: agent drafts → doctor confirms via API.

## 3. Locked decisions (from requirement Q&A)

| # | Area | Decision |
|---|---|---|
| 1 | LLM + embeddings | Gemini — `gemini-flash-latest` (chat/tools), fallback `gemini-3.8-flash`; `gemini-embedding-001` @ **768 dims** |
| 2 | Vector DB | **Chroma** (persistent local dir `backend/.chroma/`) |
| 3 | Relational DB | **Postgres = Neon**, `database_url` in `RAG/medivault/.env` |
| 4 | Hybrid retrieval | Chroma dense + Postgres FTS (`to_tsvector('simple', …)` — `simple` because Urdu has no stemmer) fused by **RRF, k=60** |
| 5 | GraphRAG | **Postgres as graph** — relational edges + traversal service (`retrieval/graph.py`). No Neo4j. |
| 6 | Agent engine | **LangGraph** (1.2.12 already in workspace env) + `langchain-google-genai` |
| 7 | Write safety | **Confirm-before-save** — `record_consultation` tool creates `status='draft'` row + `confirm_required` SSE event; `POST /consultations/confirm` commits |
| 8 | PDF types | Two only: **medicine catalogs** + **patient records**, language **mixed English/Urdu** (Roman-Urdu names → stored in `aliases` jsonb) |
| 9 | Sales input | **CSV upload**, fixed schema `sale_date, item_name, quantity, unit_price` |
| 10 | Frontend | **Strict API-only** (SSE; tested via curl/HTTPie). No UI in v1. |
| 11 | Auth | **Single doctor, no authentication** (caveat: PHI sits on Neon — training use only) |
| 12 | Patient history recall | **Agent decides via tools** (`get_patient_record` + `get_patient_history`), but system prompt makes loading patient context **mandatory before any recommendation**, enforced by a **guardrail edge** in the graph |
| 13 | Tooling | ruff (format+lint) + mypy + pytest |

## 4. Repo facts (read before running anything)

- Workspace member: `RAG/medivault/backend` (declared in root `pyproject.toml`).
- **Never run bare `uv sync` inside the member** — it prunes sibling projects.
  Always from repo root: `uv sync --all-packages --all-groups`.
- Python **3.14.1**, uv 0.12.10, Windows.
- `.env` lives at `RAG/medivault/.env` (gitignored). Required keys: `database_url`, `gemini_api_key`.
- Neon DSN is bare `postgresql://…` — app adds `+asyncpg` in code.

## 5. Architecture

```
doctor ──POST /chat (SSE)──▶ FastAPI
                              │
                              ▼
                    LangGraph agent loop (max 8 steps)
                    ┌─────────────────────────────────────┐
                    │ agent node  ──▶ tool_calls? ──▶ tools │
                    │      ▲                      │        │
                    │      └──────────────────────┘        │
                    │ guardrail (rec asked but no patient  │
                    │   loaded? ──▶ back to tools)         │
                    │      ▼                               │
                    │ generate (cited answer + JSON sidecar)│
                    └─────────────────────────────────────┘
                              │
        ┌─────────────────────┼──────────────────────┐
        ▼                     ▼                      ▼
  retrieval/hybrid       retrieval/graph        services/*
  (dense ∪ FTS → RRF)    (patient→conditions    (consultations,
        │                 →medicines→interact    sales, memory,
        ▼                 →allergy filter)       confidence)
  Chroma collections           │
  medicine_chunks              ▼
  patient_chunks         Postgres (Neon)
  consultation_memory    documents, document_chunks (tsv),
                          medicines, medicine_interactions,
                          patients, consultations (draft|committed),
                          sales, sales_uploads,
                          conversations, messages,
                          message_citations, message_tool_calls
```

**Ingest:** upload → `processing` → pypdf → type-aware chunker (medicine: per-entry;
patient: per-patient-block) → Chroma upsert + Postgres chunks (generated tsv) → LLM
structured extraction → `medicines` / `patients` rows + interaction/allergy edges → `indexed`.

**Chat:** recency-window turns always loaded; older turns available via
`consultation_memory` hybrid search tool. Retrieval runs for the prompt; agent may call
tools; final answer streams tokens, then `confidence`, optional `confirm_required`, `done`.

## 6. Folder map (`backend/src/medivault/`)

```
main.py            app factory, CORS, routers, lifespan
config.py          pydantic-settings (env: RAG/medivault/.env)
dependencies.py    DI: session, chroma, llm, services
routers/           health, documents, medicines, patients,
                   consultations, sales, chat, conversations
schemas/           one module per domain + common.py
db/
  session.py       async engine + session factory
  models/          document, medicine, patient, consultation,
                   sale, conversation  (one file each, <500 lines)
vectorstore/       chroma.py (client), collections.py (names/meta keys)
ingestion/         pdf_loader, chunker, extractor, pipeline
retrieval/         dense, sparse, fusion (RRF), hybrid, graph
agents/            graph.py (LangGraph wiring), state.py, prompts.py,
                   tools/ (registry, medicine, patient, consultation, sales)
services/          document, medicine, patient, consultation,
                   sales, conversation, memory, confidence
llm/               chat.py (model factory), embeddings.py
utils/             text, sse, ids, errors, logging
tests/             unit/ (fusion, chunker, confidence, csv, prompts),
                   integration/ (db + chroma, marked live)
```

**Rule: no file > 500 lines.** Split domain packages rather than grow files.

## 7. Data model (Postgres)

| Table | Key columns |
|---|---|
| `documents` | doc_type(`medicine\|patient`), filename, status(`uploaded\|processing\|indexed\|failed`), page_count, error, indexed_at |
| `document_chunks` | document_id, chunk_index, content, **tsv generated** (`to_tsvector('simple', content)`), meta jsonb, chroma_id |
| `medicines` | generic_name, brand_name, aliases jsonb (Urdu/brand), drug_class, indications, dosage, route, contraindications, warnings, side_effects, source_document_id |
| `medicine_interactions` | medicine_a_id, medicine_b_id, severity, description |
| `patients` | full_name, aliases jsonb, dob, gender, blood_group, allergies jsonb, conditions jsonb, source_document_id |
| `consultations` | patient_id, chief_complaint, diagnosis, recommended jsonb, notes, follow_up_date, **status(`draft\|committed\|cancelled`)**, confidence |
| `sales` / `sales_uploads` | sale_date, item_name, quantity, unit_price, total; batch + row errors |
| `conversations` / `messages` | chat threads; message has confidence |
| `message_citations` | message_id, source_type(`medicine_chunk\|patient_chunk\|consultation\|structured`), ref_id, snippet, score, rank |
| `message_tool_calls` | message_id, tool_name, args jsonb, result_summary, status — agent audit trace |

**Chroma collections:** `medicine_chunks`, `patient_chunks`, `consultation_memory`
(metadata: doctor-free single-tenant; keep `patient_id`, `conversation_id`, `role`, `document_id`, `chunk_index`).

## 8. Agent tool catalog

| Tool | R/W | Purpose |
|---|---|---|
| `search_medicines(query, k)` | R | hybrid search over medicine KB |
| `search_patients(name, k)` | R | resolve patient by name/alias (Urdu-aware) |
| `get_patient_record(patient_id)` | R | structured demographics, allergies, conditions |
| `get_patient_history(patient_id, limit)` | R | committed consultations, newest first |
| `check_interactions(medicine_ids\|names)` | R | pairwise interaction + allergy flags |
| `search_documents(query, doc_type?, k)` | R | raw chunk search (medicine/patient PDFs) |
| `search_memory(query, conversation_id?, k)` | R | older chat turns (hybrid) |
| `record_consultation(...)` | **W** | creates `draft` row, emits `confirm_required` |
| `get_sales_summary(item_name?, from_date?, to_date?)` | R | aggregated sales figures (per-item qty + revenue) |

## 9. Contracts

### SSE events (`POST /chat`)

```
event: meta              data: {conversation_id, message_id}
event: patient_context   data: {patient_id, name} | null
event: tool_call         data: {tool, args, step}
event: tool_result       data: {tool, summary}
event: sources           data: {sources:[{rank, ref_type, ref_id, title, snippet, score}]}
event: token             data: {text}
event: confidence        data: {score, level: high|medium|low, from_vault: bool}
event: confirm_required  data: {draft_id, payload:{...}}     (only when write tool ran)
event: done              data: {conversation_id, message_id, refused}
event: error             data: {detail}
```

### Error envelope (all non-2xx JSON)

```json
{"error": {"code": "not_found", "detail": "..."}}
```

### Key endpoints

`GET /health` · `POST /documents/upload` (multipart) · `GET /documents` · `DELETE /documents/{id}` ·
`GET|POST|PUT|DELETE /medicines…` · `GET|POST /patients` · `GET /patients/{id}/consultations` ·
`GET /consultations/{id}` · `POST /consultations/confirm {draft_id}` · `POST /sales/upload` (csv) ·
`GET /sales/summary` · `POST /chat` (SSE) · `GET /conversations` · `GET /conversations/{id}/messages`

## 10. Phase checklist

- [x] **P0** scaffold: pyproject deps, config, main.py, health, ruff/mypy/pytest wiring
      (chromadb 1.x + langchain-google-genai 4.4.0 installed fine on py3.14; `/health` →
      database=ok against Neon; sslmode/channel_binding stripped from DSN + TLS context
      passed via connect_args — asyncpg rejects libpq params)
- [x] **P1** DB models + alembic migration + Chroma client/collections
      (13 tables incl. generated `tsv` column applied to Neon via
      `alembic/versions/ea9334cb2e16_init_schema.py`; 3 chroma collections persisted
      at `backend/.chroma/`; integration tests prove schema + heartbeat)
- [x] **P2** ingest pipeline + documents router (PDF → chunks dual-write)
      (pypdf loader, block-merge + hard-split chunker, Gemini embeddings batched,
      chroma upsert + document_chunks rows with generated tsv; upload/list/get/delete
      endpoints; background task ingest; live integration test ingests a generated PDF
      and proves FTS match + chroma count parity)
- [x] **P3** LLM structured extraction → medicines/patients rows + graph edges
      (Gemini with_structured_output; extraction wired into ingest pipeline as
      best-effort post-step; medicines/patients CRUD routers; live test extracted
      Paracetamol+Ibuprofen rows and 2 interaction edges from a generated PDF;
      deleting a document now also deletes its extracted rows)
- [x] **P4** hybrid retrieval + graph traversal + unit tests
      (RRF fusion unit-tested; dense=Chroma cosine + sparse=Postgres FTS `simple`,
      fused + hydrated; asyncpg needs CAST(:doc_type AS text) for NULL-checks;
      graph.py: alias-aware patient resolution, condition-token candidate scoring,
      interaction lookup, allergy flags; live hybrid test passed)
- [x] **P5** LangGraph agent + tools + SSE + citations + confidence
      (StateGraph retrieve→agent→tools loop, max 8 steps; 8 tools; SSE events:
      meta/sources/tool_call/tool_result/token/confidence/confirm_required/done/error;
      confidence = dense-score blend w/ level + from_vault flag; messages, citations,
      tool-call audit persisted; **live E2E agent test passed** — recommendation +
      draft confirm + history recall + persona smalltalk)
- [x] **P6** consultation draft/confirm + patient history recall loop
      (POST /consultations/confirm|cancel, GET /consultations?patient_id&status,
      GET /patients/{id}/consultations; record_consultation tool creates status=draft;
      committed consultations surface via get_patient_history + graph past_medicines)
- [x] **P7** sales CSV module + summary tool
      (csv_loader: fixed schema + row-level errors + BOM; sales_service:
      upload/list/summary/delete with per-item aggregation; POST /sales/upload,
      GET /sales, GET /sales/summary, DELETE /sales/uploads/{id}; agent tool
      `get_sales_summary` registered (9th tool) + prompt rule 7; unit tests for
      parser edge cases; **live E2E proven**: upload → summary API + Gemini tool
      call answered "how well is Panadol selling")
- [x] **P8** polish: README, eval smoke set, error contract audit
      (backend/README.md: endpoint table, SSE curl example, test matrix;
      `tests/integration/test_eval_smoke.py` marked `eval` — 4 invariant questions
      over a seeded vault; error contract audit → added missing
      `GET /consultations/{id}` + service; `addopts` now deselects
      `integration and eval` by default; sales tests self-isolate via
      `_reset_sales_tables()`; ruff+mypy clean, 28 unit + 12 non-LLM integration
      green. **Blocked by Gemini free-tier daily quota (20 req/day on
      gemini-3.8-flash)**: LLM-dependent agent/eval/extraction tests need a
      re-run after quota reset (~8h) — previously all 4 agent+sales-agent
      integration tests passed)

## 11. Commands

```bash
# from repo root — only safe sync (never bare uv sync inside member)
uv sync --all-packages --all-groups

# from RAG/medivault/backend/
uv run ruff format . && uv run ruff check . --fix
uv run mypy src
uv run pytest -q                      # unit only (addopts deselects integration+eval)
uv run pytest -q -m integration      # live Neon/Chroma (~5 min; some need Gemini chat)
uv run pytest -q -m eval             # LLM smoke eval (~4 min; needs Gemini chat quota)
uv run alembic upgrade head
uv run uvicorn medivault.main:app --reload      # GET /health
```

## 12. Risks / gotchas

1. `chromadb` / `langchain-google-genai` wheels on **Python 3.14** — ✅ resolved:
   installed fine on py3.14, no Docker fallback needed.
2. Urdu/ Roman-Urdu: FTS uses `simple` config; dense embeddings are the primary ranker;
   patient/medicine aliases stored in jsonb and matched exactly.
3. `.env` must contain `database_url` (Neon) + `gemini_api_key` or app refuses to boot config.
4. Single-tenant by design (v1). Adding multi-doctor = add `doctor_id` everywhere + auth.
5. PHI on Neon — acceptable for training batch, not for real deployment.
6. **Gemini free-tier = 20 chat requests/day per model** (`gemini-3.8-flash`).
   Integration/eval LLM tests share this budget — heavy sessions exhaust it.
   Re-run LLM tests after quota reset (~8h) or upgrade the API plan.
   Embeddings (`gemini-embedding-001`) have a separate quota and are unaffected.
7. `addopts = "-m 'not integration and not eval'"` — plain `pytest -q` runs unit only.
   Use `-m integration` / `-m eval` to opt in (CLI `-m` overrides addopts).

## 13. Open questions log

| Date | Question | Resolution |
|---|---|---|
| 2026-10-08 | LLM provider? | Gemini (existing key) |
| 2026-10-08 | GraphRAG store? | Postgres-as-graph |
| 2026-10-08 | Agent engine? | LangGraph (user pick) |
| 2026-10-08 | Write safety? | confirm-before-save |
| 2026-10-08 | Sales input? | CSV fixed schema |
| 2026-10-08 | PDF scope? | medicines + patients only, mixed EN/UR |
| 2026-10-08 | Frontend? | strict API-only |
| 2026-10-08 | Auth? | none, single doctor |
| 2026-10-08 | History recall? | agent decides via tools + prompt/guardrail mandate |
| 2026-10-08 | Persona boundary? | always reply in medical persona, vault-first, flag general-knowledge |

## 14. Session log

| Date | What happened |
|---|---|
| 2026-10-08 | Requirements gathered, decisions locked, plan approved, context.md created, P0 scaffold started |
| 2026-10-08 | P0 complete: 8 unit tests green, ruff+mypy clean, server boots, Neon connection fixed (sslmode/channel_binding stripped, TLS via connect_args) |
| 2026-10-08 | P1 complete: schema migrated to Neon, chroma collections created, 12 tests green (unit+integration). pytest engine-per-loop leak fixed via autouse dispose fixture |
| 2026-10-08 | P3 extraction live-proven (Paracetamol+Ibuprofen rows, 2 interaction edges) |
| 2026-10-08 | P4 hybrid retrieval live-proven; asyncpg CAST fix for nullable doc_type param |
| 2026-10-08 | P5+P6 live-proven: agent recommendation flow with draft confirm + history recall + persona smalltalk, 2/2 integration tests passed |
| 2026-10-08 | P7 complete: sales CSV parser+service+router+agent tool, live-proven (API summary + Gemini tool-call answer). Full suite: 33 tests (28 unit + 5 integration), ruff+mypy clean |
| 2026-10-10 | P8 complete (modulo Gemini quota): GET /consultations/{id} added, sse_helper de-dup, eval smoke set (4 questions), error-contract audit (5 envelope tests), sales-test isolation, README full pass, addopts marker defaults. 28 unit + 12 non-LLM integration green; 8 LLM-dependent tests pending Gemini free-tier daily quota reset (~8h) |
