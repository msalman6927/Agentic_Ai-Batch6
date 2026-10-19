# context.md — Pizza World Agent (resume file for any coding agent)

> **Read this file first.** It is the single source of truth for *what exists* and *what remains*.
> After finishing a task below, change its checkbox from `[ ]` to `[x]`. Never mark a task
> done unless it is actually implemented and verified.

## 0. What this project is

A restaurant ordering agent: **LangGraph** workflow + **FastAPI** backend + **Neon** Postgres,
with a **Next.js** frontend (user chat panel, admin panel, kitchen panel).

User chats with a bot that:
- shows the menu (SQL table — **no RAG, no embeddings, no pgvector** — deliberately removed),
- builds an order (cart in graph state) and computes the total **deterministically via tools
  querying `menu_items`** (the LLM never sets a price),
- pays now or pays later (max 3 days) — two tools selected by a **conditional edge**,
- **human-in-the-loop**: a `pay_later` order with total > 7000 → `interrupt()` → admin
  approves/rejects on the admin panel → graph resumes with `Command(resume=...)`; the decision
  is saved in `state["human_feedback"]`,
- order then appears on the **kitchen panel**; the chef advances
  `placed → preparing → ready → on_ride → delivered`; every change is pushed **live over SSE**
  to the user's chat screen (no polling, **no email/SMTP** — both removed from the original plan),
- checkpoints (incl. pending interrupts) persist via **`AsyncPostgresSaver` on Neon**.

Streaming: the chat POST endpoint streams with `graph.astream(stream_mode=["messages", "updates", "custom"])`
over SSE. Dashboard notifications use an **in-process asyncio event bus** (single-process
uvicorn; upgrade path = Postgres LISTEN/NOTIFY). Every SSE stream starts with a snapshot.

## 1. Environment facts (verified)

- Repo root: `D:\Muhammad Salman\A2 skill accadey\batch_6\Agentic_Ai_Batch_6`
- This project **is a uv workspace member** (root `pyproject.toml` →
  `tool.uv.workspace.members` includes `LANGGRAPH/restaurent_flow/backend`).
- **Project/import-package rename (IMPORTANT):** the member's *project* name is
  `restaurant-agent` and the *import package* is **`pizza_world`** (under `src/pizza_world/`).
  Why: (a) uv refused two members both named `backend`, (b) both this project and Brainwise
  ship an import package named `backend` into the shared venv — `import backend` resolved to
  Brainwise's. So: project name `restaurant-agent`, module `pizza_world`, uv build-backend
  `[tool.uv.build-backend] module-name = "pizza_world"`, console script
  `pizza-world = "pizza_world.main:main"`. Do NOT rename back to `backend`.
- **Windows event loop (IMPORTANT):** psycopg async cannot run on the default
  ProactorEventLoop. All standalone entrypoints go through `pizza_world/core/runner.py`
  (`run()`) which uses a SelectorEventLoop on win32. **Start the server with
  `uv run python -m pizza_world`** — NOT `uvicorn ... --reload` (that would use
  ProactorEventLoop and crash on the first DB call).
- **uv rule (from repo AGENTS.md): never run bare `uv sync` inside a member** — it prunes the
  sibling projects. Always sync from the repo root: `uv sync --all-packages --all-groups`.
  `uv add -p <name>` fails here because two members are named `backend` — edit
  `pyproject.toml` directly instead, then root-sync. `uv run <cmd>` inside the member is safe.
- Python: 3.14.1 (member requires `>=3.14`; wheels for pydantic-core/psycopg/langgraph all
  resolved fine — no relaxation needed).
- `.env` (gitignored) in this backend dir: `database_url` (bare `postgresql://` Neon DSN),
  `openai_api_key`. Code rewrites to `postgresql+psycopg://` for SQLAlchemy
  (`Settings.async_dsn`) and keeps a bare libpq DSN (`Settings.psycopg_dsn`) for
  `AsyncPostgresSaver.from_conn_string` — **the checkpointer must get the bare DSN**.
- **Security note:** the user pasted the OpenAI key + Neon password in chat. They were told to
  rotate the OpenAI key. Never commit `.env`.
- Source menu: `Pizza_World_Menu_Text.pdf` (Pizza World, Sahiwal). Its text was already
  extracted during planning — the structured seed data in `data/menu_seed.py` is derived from
  it. The PDF itself is no longer read at runtime.
- Seeded accounts: `admin@pizzaworld.com` / `admin123`, `chef@pizzaworld.com` / `chef123`
  (overridable via `admin_email/admin_password/chef_email/chef_password` env).
  **Must use a non-reserved TLD** (`.local`/`.test` are rejected by pydantic EmailStr).

## 2. Locked design decisions (user-approved — do NOT reopen)

1. Deterministic router + tool nodes (not a ReAct agent).
2. Menu = **Postgres `menu_items` table only**; tools query it; no pgvector/RAG/embeddings.
3. Checkpointer = **`AsyncPostgresSaver` on Neon** (NOT MemorySaver — user chose durability).
4. Human feedback = dedicated **`human_feedback` node** using `interrupt()`; resume payload
   written to `state["human_feedback"] = {approved, admin_comment, admin_id, decided_at}`.
   Rule: only `pay_later` AND total > 7000 interrupts; `pay_now` never does.
5. No 2-minute timer. No email. Kitchen panel + SSE instead.
6. Chef is a **third role** (user / admin / chef); 5 chef statuses:
   `placed → preparing → ready → on_ride → delivered`.
7. Chef status changes happen **outside the graph** (plain REST + SSE publish). The agent graph
   is not re-invoked.
8. In-process asyncio **EventBus** for SSE fan-out (topics: `user:{user_id}`, `admin`, `kitchen`).
9. Simulated payment (no gateway): `pay_now` writes `payments.status='paid'`,
   `pay_later` writes `'due'` with `due_date = now + 3 days`.
10. Full JWT auth (bcrypt via pwdlib, pyjwt). Frontend = Next.js at
    `LANGGRAPH/restaurent_flow/frontend/` (npm only, NOT in the uv workspace).

## 3. Key contracts (keep stable — the frontend depends on them)

### Graph nodes
`START → router → (view_menu | add_items | show_total | pay_now | pay_later | general) →
[human_feedback if pay_later & total>7000] → persist_order → END`

### Order status lifecycle
`awaiting_approval → confirmed → placed → preparing → ready → on_ride → delivered`
(+ `rejected`, + user-`cancelled` reserved). Transitions are validated server-side (illegal → 409).

### SSE events (`event:` name → `data:` JSON)
- `token` — LLM delta `{delta}` (chat POST only)
- `node` — `{node}` ran
- `custom` — `{text}` assistant progress text
- `snapshot` — first event of every `GET .../events` stream: full current state for that panel
- `pending_approval` — `{thread_id, order_id, items, total, created_at}` (admin topic)
- `approval_decision` — `{thread_id, approved, admin_comment}` (user topic)
- `order_placed` — `{order_id, thread_id, user_id, total, payment_mode}` (admin + kitchen topics)
- `order_status` — `{order_id, status, changed_at}` (user + kitchen + admin topics)
- `interrupt` — `{payload}` on the chat POST stream, then stream closes (reason: awaiting approval)

### REST
```
POST /api/v1/auth/register | login                      -> {access_token, role}
POST /api/v1/chat                       SSE  [user]     {message, thread_id?}
GET  /api/v1/threads/{id}/events        SSE  [user]
GET  /api/v1/chat/threads/{id}/messages [user]
GET  /api/v1/orders                     [user]
GET  /api/v1/menu                       [user]
GET  /api/v1/admin/pending-approvals    [admin]
POST /api/v1/admin/decide               [admin]  {thread_id, approved, admin_comment}
GET  /api/v1/admin/orders               [admin]
GET  /api/v1/admin/events               SSE  [admin]
GET  /api/v1/kitchen/orders             [chef]
PATCH /api/v1/kitchen/orders/{id}/status [chef]  {status}
GET  /api/v1/kitchen/events             SSE  [chef]
GET  /api/v1/health
```

### ChatState fields
`messages` (add_messages), `cart: list[CartLine]`, `total: float`,
`payment_mode: "now"|"later"|None`, `due_date: str|None`, `order_id: str|None`,
`human_feedback: dict|None`, `user_id: str`, `reply: str`.

### DB tables
`users`, `menu_items`, `orders`, `order_items`, `payments`, `chat_messages`
(see `src/backend/db/models.py`; schema is created with `create_all` on startup — no Alembic).

### Config env vars (in `.env`)
`database_url`, `openai_api_key`, `jwt_secret`, `admin_email`, `admin_password`,
`chef_email`, `chef_password`, `borrow_threshold` (7000), `llm_model` (gpt-4o-mini),
`embedding_model` unused (no embeddings), `cors_origins`.

## 4. Packages

Backend (added via `uv add -p backend` from repo root):
`langgraph`, `langchain`, `langchain-openai`, `langgraph-checkpoint-postgres`,
`psycopg[pool]`, `psycopg-binary`, `sqlalchemy[asyncio]`, `pydantic-settings`,
`fastapi[standard]`, `pwdlib[bcrypt]`, `pyjwt`, `httpx`;
dev group: `ruff`, `mypy`, `pytest`, `pytest-asyncio`.
Frontend: `npx create-next-app@latest frontend` (TS, App Router, Tailwind).

**Removed from the original plan — do not re-add:** `langchain-postgres`, pgvector,
`pypdf` (seed data is static), `aiosmtplib`/SMTP, MemorySaver, `asyncio.sleep` notify node.

## 5. Task list — mark `[x]` when DONE (and verified)

### Phase 0 — scaffolding
- [x] 0.1 Add backend deps + dev deps (edited pyproject.toml + `uv sync --all-packages --all-groups` from root)
- [x] 0.2 `src/pizza_world/config.py` — pydantic-settings (`Settings` singleton) incl. DSN rewrite
      to `postgresql+psycopg://` + `psycopg_dsn` (bare libpq DSN for the checkpointer)
- [x] 0.3 `src/pizza_world/db/session.py` — async engine + `async_session_maker`
- [x] 0.4 `src/pizza_world/main.py` — FastAPI app, CORS, lifespan (create tables), `/api/v1/health`
- [x] 0.5 Verify: server boots, `/api/v1/health` returns 200

### Phase 1 — data
- [x] 1.1 `src/pizza_world/db/models.py` — User/Menu/Order/OrderItem/Payment/ChatMessage + enums
- [x] 1.2 `src/pizza_world/seed.py` — `python -m pizza_world.seed`: create tables, seed menu_items
      (66 rows from the PDF, PKR prices), seed admin + chef from env
- [x] 1.3 Ran seed against Neon; verified 66 menu items, 2 users, 0 orders

### Phase 2 — tools (deterministic, DB-backed)
- [x] 2.1 `src/pizza_world/agents/tools.py` — `view_menu(session, category?)`,
      `add_items(session, cart, extracted_items)` (resolve against menu_items, fuzzy match,
      reject unknown), `calculate_total(cart)`, `pay_now`, `pay_later` (due_date +3d)
- [x] 2.2 Verified: 2× Chicken Tikka Medium + 1 Zinger Burger = **Rs.2150** exact

### Phase 3 — graph + checkpointer
- [x] 3.1 `src/pizza_world/agents/state.py` — `ChatState` + `CartLine`
- [x] 3.2 `src/pizza_world/agents/router.py` — LLM JSON intent classifier (1 retry, fallback)
      **NOTE: OpenAI key in .env is invalid (401) → router degrades to a deterministic keyword
      fallback (`_fallback_classify`). Once a valid key is in .env, the LLM path is used
      automatically (circuit breaker `_llm_disabled` flips off on process restart).**
- [x] 3.3 `src/pizza_world/agents/nodes.py` — all nodes incl. human_feedback interrupt
- [x] 3.4 `src/pizza_world/agents/graph.py` — `build_graph()` + conditional edges
- [x] 3.5 `src/pizza_world/services/checkpointer.py` — AsyncPostgresSaver singleton (**must
      use `settings.psycopg_dsn`, the bare libpq DSN — the +psycopg scheme breaks psycopg**)
- [x] 3.6 Script test passed (`uv run python -m pizza_world.tests.e2e_graph`):
      menu/cart/total/pay_now/borrow-interrupt-approve/borrow-reject all green
- [x] **API gotcha fixed:** this langgraph version takes the `Command` as the **input arg** of
      `astream(Command(resume=...), config)` — NOT as a `command=` kwarg (silently ignored).

### Phase 4 — auth
- [x] 4.1 `src/pizza_world/core/security.py` — pwdlib **BcryptHasher only** (recommended()
      needs argon2, not installed), JWT, `require_role` deps
- [x] 4.2 `src/pizza_world/api/v1/auth.py` — register/login
- [x] 4.3 Verified over HTTP: register user + login admin + login chef + role guard
      (user → admin endpoint = 403)

### Phase 5 — event bus + chat SSE
- [x] 5.1 `src/pizza_world/services/bus.py` — EventBus (subscribe/publish, topic helpers)
- [x] 5.2 `src/pizza_world/services/messages.py` — persist chat_messages helpers
- [x] 5.3 `src/pizza_world/api/v1/chat.py` — POST /chat SSE + GET /threads/{id}/events
      (snapshot + live) + GET messages + GET /menu + GET /orders
- [x] 5.4 Verified: SSE token/node/interrupt/done events streamed correctly

### Phase 6 — admin API
- [x] 6.1 `src/pizza_world/api/v1/admin.py` — pending-approvals (**reads `pending_approvals`
      table**, not checkpointer scan — was timing out on Neon), decide (background resume),
      orders list
- [x] 6.2 GET /admin/events (snapshot + live)
- [x] 6.3 Verified full interrupt → decide → resumed order loop

### Phase 7 — kitchen API
- [x] 7.1 `src/pizza_world/api/v1/kitchen.py` — board, PATCH status w/ transition validation
      (placed→preparing→ready→on_ride→delivered, illegal → 409), chat_message + SSE publish
- [x] 7.2 GET /kitchen/events (snapshot + live)
- [x] 7.3 Verified: chef advanced order through all 4 statuses; user received 4 announcements

### Phase 8 — frontend
- [ ] 8.1 Scaffold `LANGGRAPH/restaurent_flow/frontend/` with create-next-app
- [ ] 8.2 `lib/api.ts` — auth + SSE-over-fetch helper (Authorization header)
- [ ] 8.3 `/` user chat panel (streaming, cart chip, interrupt banner, live status line)
- [ ] 8.4 `/admin` panel (live pending approvals, approve/reject, orders table)
- [ ] 8.5 `/kitchen` panel (live board, next-transition buttons)
- [ ] 8.6 Verify all three panels end-to-end in the browser

### Phase 9 — quality gate
- [x] 9.1 `uv run ruff format . && uv run ruff check . --fix` — **clean**
- [x] 9.2 `uv run mypy src` — **clean** (33 files, 0 errors; targeted `type: ignore[call-overload]`
      on `graph.astream(..., stream_mode=[...])` calls — a langgraph typing limitation)
- [x] 9.3 `uv run pytest -q` — **11 passed** (`tests/test_unit.py`: cart totals, fallback router,
      intent routing, HITL threshold edges, kitchen transition map)
- [x] 9.4 E2E verified: `python -m pizza_world.tests.e2e_graph` (graph-level) and
      `python -m pizza_world.tests.e2e_http` (HTTP: auth/SSE/interrupt/decide/kitchen) — both green
- [ ] 9.5 Frontend build (Phase 8) + final end-to-end in browser

## 6. Run commands

```bash
# backend (from backend dir)
uv run python -m pizza_world                        # start API on port 8000 (Windows-safe; use THIS, not uvicorn CLI)
uv run python -m pizza_world.seed                   # tables + menu + admin/chef
uv run pytest -q ; uv run mypy src ; uv run ruff format . ; uv run ruff check . --fix

# frontend (from restaurent_flow/frontend)
npm run dev                                       # port 3000
```

## 7. Known risks

- Python 3.14 wheels: if `uv add` fails on pydantic-core/psycopg/langgraph, relax member
  `requires-python` to `>=3.12` and re-run from the repo root.
- EventBus is single-process: run uvicorn **without** `--workers`.
- Neon connection pool limits: keep pool_size small (5) + `pool_timeout=30`.

---

## Progress log (append-only, newest last)

- 2026-10-19: Plan approved by user. context.md created. Phase 0 started.
