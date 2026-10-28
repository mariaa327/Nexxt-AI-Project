# AGENTS.md

Instructions for coding agents working in this repository. Read this before making changes.
Product context: `PLAN.md` (what and why), `DECISIONS.md` (non-obvious choices), `PROGRESS.md` (status).

## Architecture

Monorepo with two independently deployable services:

- `frontend/` — Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4. One dashboard page at `/`.
- `backend/` — FastAPI, Pydantic v2, SQLAlchemy 2.x, boto3 (Claude on Amazon Bedrock).
- Fictional clients log in (username + password). Each has their **own PostgreSQL database** `client_<username>`, seeded from `backend/app/data/users/<username>.json`; `bank_directory` holds only logins. PostgreSQL runs as the `db` service in Docker Compose.

Request flow: browser → `POST /api/auth/login` (directory DB, signed token) → `GET /api/dashboard` with `Authorization: Bearer` (token → user → that user's database → deterministic engine) → `POST /api/agent/analyze` (engine → `BillDecision` → Claude phrases it, or the rules fallback; analysis saved in the user's DB) → `POST /api/agent/execute/initiate` (verification challenge owned by the user, auto-approved after `DEMO_APPROVAL_SECONDS`) → `POST /api/agent/execute` (apply and save to the user's DB) → `POST /api/agent/reset` (re-seed the user's DB).

Backend layers (keep them separate):

| Layer | Location | Rule |
| --- | --- | --- |
| API | `app/api/endpoints/`, `app/api/deps.py` | Thin. Validate and delegate. No SQL, no provider SDK calls, no try/except for service errors (a handler in `app/main.py` maps them). |
| Schemas | `app/schemas/` | `banking.py` (data file), `insights.py` (engine output, LLM output, API responses). Never import SQLAlchemy. |
| Services | `app/services/` | `banking/` is the deterministic engine (works on `ClientSnapshot` only, no DB access); `ai_agent.py` talks to the model; `client_repository.py` maps a user's DB to/from `ClientSnapshot`; `provisioning.py` creates and seeds databases; `auth.py` logs in. Raise `AgentServiceError` subclasses from `errors.py`, never raw SDK errors. |
| Models | `app/models/` | `directory.py` (`DirectoryBase`, logins) and `client.py` (`ClientBase`, one client's tables). Never import API schemas. |
| Core | `app/core/` | Settings, `DatabaseRouter` (one engine per database), password hashing and session tokens. |

## Engine rules (do not break these)

- **The LLM never computes.** All amounts, dates and rankings come from `app/services/banking/`. The model receives only the `BillDecision` JSON — never raw transactions — and its draft is rejected (rules fallback) if it names another option or an amount not present in the decision.
- **Money is `Decimal`.** Parse with `Decimal(str(x))`; round once with `round_money` at the end of a calculation, never inside a loop.
- **Overdraft interest accrues on each day's negative balance**, not on the peak.
- **Each option is priced as if it were the only action taken.**
- **Isolation:** data endpoints get the client's DB session only through `get_client_session` (resolved from the token). Never open a client database from a username taken from the request.
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

Both, with Docker: `docker compose up --build` from the repository root. Database only: `docker compose up -d db`; re-seed: `cd backend && python -m app.seed --reset`.

## Environment variables

- All configuration comes from environment variables; never hardcode secrets or URLs.
- `.env.example` files are committed; `.env`, `.env.local` and other real env files are gitignored.
- Backend settings live in `app/core/config.py`. Add a field there (with a safe default) instead of reading `os.environ` elsewhere.
- Frontend variables must start with `NEXT_PUBLIC_` and are public by definition. Never expose an API key or database URI through them.
- AWS credentials go only in gitignored `.env` / `backend/.env`, never in `.env.example`.
- Never log keys, passwords or secret values, and never return provider errors or stack traces to clients.

## Conventions

- Python: type annotations everywhere, `ruff check` and `ruff format` clean, 4-space indent, module docstrings where the module's role is not obvious.
- TypeScript: `strict` mode, no `any`, typed API responses mirrored in `src/lib/types.ts`, client components marked with `"use client"`.
- Add dependencies only when required by a concrete feature; do not add workflow engines, queues, caches or vector stores speculatively. The projection chart is plain SVG on purpose.
- Startup provisioning (`PROVISION_ON_STARTUP`) is a development convenience. Production schema changes need migrations.
- Demo-grade auth only. Do not load real client data into it.

## Verifying changes

Before reporting work as done, run the checks that cover what you touched:

- Backend: `python -m pytest` (tests must pass without PostgreSQL or AI credentials: they use SQLite per user) and ruff.
- Frontend: `npm run lint && npm run typecheck && npm run build`.
- Anything touching configuration or Docker: `docker compose config`, and `docker compose up --build` when practical.

If a check cannot run in the current environment, say so explicitly rather than assuming it passes. Do not commit secrets or real `.env` files.
