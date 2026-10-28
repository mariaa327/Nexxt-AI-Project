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
- [ ] Run with a real `OPENAI_API_KEY` (not tested: no key configured)
- [ ] Run with a real `DATABASE_URL` (persistence tested against SQLite only)
