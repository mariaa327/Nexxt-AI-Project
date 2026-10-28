# AGENTS.md

Instructions for coding agents working in this repository. Read this before making changes.
Product context: `PLAN.md` (what and why), `DECISIONS.md` (non-obvious choices), `PROGRESS.md` (status).

## Architecture

Monorepo with two independently deployable services:

- `frontend/` — Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4. One dashboard page at `/`.
- `backend/` — FastAPI, Pydantic v2, SQLAlchemy 2.x, OpenAI SDK.
- There is **no authentication**: the app serves one demo client from `backend/app/data/client1_date.json`.
- PostgreSQL is optional and external (no database container). Without `DATABASE_URL`, analyses are simply not stored.

Request flow: browser → `GET /api/dashboard` (deterministic engine only) → `POST /api/agent/analyze` (engine → `BillDecision` → LLM phrases it, or the rules fallback) → best-effort row in `agent_tasks` → `POST /api/agent/execute` applies the chosen option in memory → `POST /api/agent/reset` restores the data file.

Backend layers (keep them separate):

| Layer | Location | Rule |
| --- | --- | --- |
| API | `app/api/endpoints/`, `app/api/deps.py` | Thin. Validate and delegate. No SQL, no provider SDK calls, no try/except for service errors (a handler in `app/main.py` maps them). |
| Schemas | `app/schemas/` | `banking.py` (data file), `insights.py` (engine output, LLM output, API responses). Never import SQLAlchemy. |
| Services | `app/services/` | `banking/` is the deterministic engine; `ai_agent.py` talks to the model; `persistence.py` stores analyses. Raise `AgentServiceError` subclasses from `errors.py`, never raw SDK errors. |
| Models | `app/models/` | SQLAlchemy persistence only. Never import API schemas. |
| Core | `app/core/` | Settings and engine/session. |

## Engine rules (do not break these)

- **The LLM never computes.** All amounts, dates and rankings come from `app/services/banking/`. The model receives only the `BillDecision` JSON — never raw transactions — and its draft is rejected (rules fallback) if it names another option or an amount not present in the decision.
- **Money is `Decimal`.** Parse with `Decimal(str(x))`; round once with `round_money` at the end of a calculation, never inside a loop.
- **Overdraft interest accrues on each day's negative balance**, not on the peak.
- **Each option is priced as if it were the only action taken.**
- **Scope:** the agent decides how to cover the imminent shortfall. It does not give advice on past spending or future budgeting.

## Commands

Backend (run from `backend/`; the virtualenv lives at the repository root):

```bash
python -m venv ../.venv && source ../.venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
python -m pytest
ruff check app tests && ruff format --check app tests
```

Frontend (run from `frontend/`):

```bash
npm ci
npm run dev
npm run lint
npm run typecheck
npm run build
```

Both, with Docker: `docker compose up --build` from the repository root.

## Environment variables

- All configuration comes from environment variables; never hardcode secrets or URLs.
- `.env.example` files are committed; `.env`, `.env.local` and other real env files are gitignored.
- Backend settings live in `app/core/config.py`. Add a field there (with a safe default) instead of reading `os.environ` elsewhere.
- Frontend variables must start with `NEXT_PUBLIC_` and are public by definition. Never expose an API key or database URI through them.
- Never log keys, passwords or secret values, and never return provider errors or stack traces to clients.

## Conventions

- Python: type annotations everywhere, `ruff check` and `ruff format` clean, 4-space indent, module docstrings where the module's role is not obvious.
- TypeScript: `strict` mode, no `any`, typed API responses mirrored in `src/lib/types.ts`, client components marked with `"use client"`.
- Add dependencies only when required by a concrete feature; do not add workflow engines, queues, caches or vector stores speculatively. The projection chart is plain SVG on purpose.
- Automatic table creation (`AUTO_CREATE_TABLES`) is a development convenience. Production schema changes need migrations.
- This demo has no access control. Do not load real client data into it as-is.

## Verifying changes

Before reporting work as done, run the checks that cover what you touched:

- Backend: `python -m pytest` (tests must pass without database or AI credentials) and ruff.
- Frontend: `npm run lint && npm run typecheck && npm run build`.
- Anything touching configuration or Docker: `docker compose config`, and `docker compose up --build` when practical.

If a check cannot run in the current environment, say so explicitly rather than assuming it passes. Do not commit secrets or real `.env` files.
