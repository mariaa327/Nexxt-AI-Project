# PROGRESS

Live checklist for the work in `PLAN.md`. Decisions behind it are in `DECISIONS.md`.

Baseline (2026-10-28): backend `pytest` — 33 passed, no credentials.

## Backend

- [x] 1. Fixture extended at `backend/app/data/client1_date.json` (root original kept unchanged)
- [x] 2. Schemas: `schemas/banking.py`, `schemas/insights.py`; `services/banking/loader.py`
- [x] 3. `categorizer.py`, `recurring.py`, `projection.py`, `options.py` with unit tests
- [x] 4. `engine.py` + `GET /api/dashboard`
- [x] 5. `ai_agent.py` rewrite + `POST /api/agent/analyze` with rules fallback
- [x] 6. `executor.py` + `POST /api/agent/execute` (+ `POST /api/agent/reset` for the demo)
- [x] 7. Auth removed: `security.py`, Supabase settings, `pyjwt`, `test_security.py`

Backend status: 43 tests pass, `ruff check` and `ruff format --check` clean.

## Frontend

- [x] 8. Supabase removed: `proxy.ts`, `lib/supabase/`, login page, dependencies
- [x] 9. Dashboard: balances, upcoming bills, projection chart, recommendation, apply, before/after

## Config and docs

- [x] 10. `.env.example` files, `frontend/Dockerfile`, `docker-compose.yml`
- [x] 11. `README.md` and `AGENTS.md` updated

## Verification

- [x] Backend tests green (43), ruff clean
- [x] Frontend lint, typecheck, build green
- [x] `docker compose config` valid; `docker compose build` succeeds; fixture present in the backend image
- [x] Live API run: analyze → execute credit card → no risk → reset
- [x] Visual check of the dashboard in a browser (by the team, 2026-10-28)
- [x] Real AI provider tested (Amazon Bedrock, see iteration 3)
- [ ] Run with a real `DATABASE_URL` (persistence tested against SQLite only)

## Iteration 2 — real AI wording, mobile-first, payment verification

- [x] Docs integrity pass (D6 wording, PLAN architecture)
- [x] Provider timeout + prompt names where the money is
- [x] Verification challenge: backend endpoints, errors, tests
- [x] Verification modal (app approval) in the frontend
- [x] Mobile-first order: chart, then recommendation; hero text removed; responsive chart
- [x] Live AI via Amazon Bedrock (Claude Sonnet 5.5): 6/6 scenarios `generated_by: "llm"`
- [ ] Team check of the new screens in a browser (phone view)

## Iteration 3 — Bedrock and dynamic data

- [x] AI provider switched to Amazon Bedrock; credentials moved out of the committed `.env.example`
- [x] Edge-case scenario files + `/api/scenarios` (list, load, upload)
- [x] Scenario dropdown and JSON upload in the dashboard
- [x] Backend 67 tests, ruff clean; frontend lint, typecheck, build green
- [ ] Team check in a browser: switch scenarios, upload a file, apply with verification

## Iteration 4 — fictional users with their own databases

- [x] Seed file per user (`backend/app/data/users/`), scenario dropdown and upload removed
- [x] PostgreSQL in Docker Compose; directory DB + one DB per user, created and seeded on startup
- [x] Login (scrypt passwords, signed tokens), per-user data access, per-user payment confirmations
- [x] Applying an option is saved; reset re-seeds the user's DB
- [x] Login page with demo accounts; navbar with name and log out
- [x] Backend 77 tests (SQLite per user, no Postgres/AWS needed), ruff clean; frontend lint, typecheck, build
- [x] Verified on real PostgreSQL and the full Docker stack (login, isolation, persistence, Bedrock)
- [ ] Team check in a browser: log in as each user, apply, log out and in again, reset
