# Agentic Ai Batch 6 — Agent Guide

Repo of a training batch: several **unrelated** projects live side by side. Do not move code
between them, do not "consolidate" their dependencies, and do not assume one project's
conventions apply to another.

## Map

| Path | What it is |
|---|---|
| `fastapi/Brainwise/` | **Active build.** Study bot: `backend/` (FastAPI, uv workspace member) + `frontend/` (Next.js 16 / React 19 / Tailwind 4, separate npm project) |
| `fastapi/academy project/` | Finished CRUD API, uv workspace member, Postgres via SQLAlchemy async + Alembic |
| `fastapi/library_system/` | Standalone practice scripts — no manifest, not in the workspace |
| `fastapi/*.py` | Loose FastAPI snippets (`basics_api.py`, `crud.py`, `parameters.py`) |
| `prompt_Engineering/`, `python/` | Course notes and learning snippets — never import from them |
| `src/agentic_ai_batch_6/` | Empty placeholder package of the root project |

**Read before editing:**

- `fastapi/Brainwise/backend/AGENTS.md` — authoritative Brainwise spec (phase state machine,
  deterministic IQ table, prompt/tool rules, SSE + error contract, layering). It wins over this
  file for Brainwise decisions.
- `fastapi/academy project/AGENTS.md` — academy-specific rules.

## uv workspace — read before running any uv command

Root `pyproject.toml` declares two members: `fastapi/academy project` and
`fastapi/Brainwise/backend`. Both share one `.venv` at the repo root. Python **3.14.1**.

```bash
# from the repo root — the only safe way to install
uv sync --all-packages --all-groups
```

**Gotcha (verified):** a bare `uv sync` executed *inside* a member prunes the sibling project's
packages — it silently uninstalls `academy-project`, `psycopg`, and `pyjwt`. `uv run <cmd>`
inside a member is safe and does not prune. Lint/type/test tools live in the `dev` group of
`fastapi/Brainwise/backend/pyproject.toml` and install only with `--all-groups`.

## Verification

Brainwise backend — run from `fastapi/Brainwise/backend/`:

```bash
uv run ruff format . && uv run ruff check . --fix   # format first, then lint
uv run mypy src                                     # pydantic.mypy plugin is configured
uv run pytest -q
uv run uvicorn backend.main:app --reload            # GET /api/v1/health
```

Academy API — run from `fastapi/academy project/` (quote the path; it contains a space):

```bash
uv run uvicorn main:app --reload                    # GET /
```

Academy has no test suite and no linter configured — never claim a clean `pytest`/`ruff` run
there. Frontend: `npm run dev` (port 3000) and `npm run lint` from `fastapi/Brainwise/frontend/`.

## Environment and secrets

- Three `.env` files, all gitignored: repo root (**empty, 0 bytes — not the Brainwise config**),
  `fastapi/academy project/.env` (`database_url`), `fastapi/Brainwise/backend/.env`
  (`database_url`, `openai_api_key`).
- `database_url` is a bare `postgresql://` DSN. Each app chooses its async driver in code
  (`+psycopg` for academy, `+asyncpg` for Brainwise) — don't rewrite the DSN in `.env`.
- Academy's `config/db.py` reads `database_url` at **import time**: missing env, app won't boot.
- **`fastapi/academy project/alembic.ini` carries a committed Neon username and password.** Treat
  it as leaked (rotate it), never copy that pattern, and keep every `sqlalchemy.url` a placeholder.
- Never commit `.env`; `.gitignore` also covers `__pycache__/`, `.venv/`, and tool caches.

## Git

- `uv.lock` is tracked: commit it when dependencies change, never churn it otherwise.
- History is one commit per project task (`add databases`, `add file uploading`, …) — keep a
  change scoped to a single project.
