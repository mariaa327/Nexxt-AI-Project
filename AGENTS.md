# AGENTS.md

Instructions for coding agents working in this repository. Read this before making changes.

## Architecture

Monorepo with two independently deployable services:

- `frontend/` — Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4.
- `backend/` — FastAPI, Pydantic v2, SQLAlchemy 2.x, PyJWT.
- PostgreSQL and Auth are hosted by Supabase; there is no database container.

Request flow: browser → Next.js (`src/proxy.ts` refreshes the Supabase session) → `POST /api/agent/run` on FastAPI with `Authorization: Bearer <access_token>` → JWT verified in `app/core/security.py` → agent service → row in `agent_tasks` → structured JSON back to the UI.

Backend layers (keep them separate):

| Layer | Location | Rule |
| --- | --- | --- |
| API | `app/api/endpoints/` | Thin. Validate, delegate, translate errors. No SQL, no provider SDK calls. |
| Schemas | `app/schemas/` | Pydantic request/response/structured-output models. Never import SQLAlchemy. |
| Services | `app/services/` | Business logic and provider calls. Raise `AgentServiceError` subclasses, never raw SDK errors. |
| Models | `app/models/` | SQLAlchemy persistence only. Never import API schemas. |
| Core | `app/core/` | Settings, engine/session, JWT verification. The only place auth is implemented. |

## Commands

Backend (run from `backend/`):

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
python -m pytest
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
- Frontend variables must start with `NEXT_PUBLIC_` and are public by definition. Never expose an API key, database URI or JWT secret through them.
- Never log tokens, passwords or secret values, and never return provider errors or stack traces to clients.
- Backend auth uses JWKS with asymmetric keys by default. `SUPABASE_JWT_SECRET` (HS256) is a legacy compatibility path only.

## Conventions

- Python: type annotations everywhere, `ruff check` and `ruff format` clean, 4-space indent, module docstrings where the module's role is not obvious.
- TypeScript: `strict` mode, no `any`, typed API responses, client components marked with `"use client"`.
- Add dependencies only when required by a concrete feature; do not add workflow engines, queues, caches or vector stores speculatively.
- Automatic table creation (`AUTO_CREATE_TABLES`) is a development convenience. Production schema changes need migrations.
- The FastAPI backend is the authorization boundary. The Next.js proxy only refreshes sessions; never rely on it to protect data.

## Verifying changes

Before reporting work as done, run the checks that cover what you touched:

- Backend logic or auth: `python -m pytest` (tests must pass without Supabase or AI credentials).
- Frontend: `npm run lint && npm run typecheck && npm run build`.
- Anything touching configuration or Docker: `docker compose config`, and `docker compose up --build` when practical.

If a check cannot run in the current environment, say so explicitly rather than assuming it passes. Do not commit secrets or real `.env` files.
