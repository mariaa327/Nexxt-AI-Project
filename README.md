# AI Hackathon Starter

A small, reusable monorepo for building an AI feature fast: Next.js 16 frontend, FastAPI backend, Supabase for Auth and PostgreSQL, and the native OpenAI Python SDK with structured outputs.

The example feature is a single agent endpoint (`POST /api/agent/run`) that answers a prompt, persists the result per user, and renders it in the UI. Replace that feature with your hackathon idea; the plumbing stays.

---

## Contents

- [What works without credentials](#what-works-without-credentials)
- [Stack and versions](#stack-and-versions)
- [Repository structure](#repository-structure)
- [Local setup](#local-setup)
- [Running the servers](#running-the-servers)
- [Checks and tests](#checks-and-tests)
- [Docker Compose](#docker-compose)
- [Configuring real integrations](#configuring-real-integrations)
- [Troubleshooting](#troubleshooting)

---

## What works without credentials

| Capability | Without credentials | Needs configuration |
| --- | --- | --- |
| Frontend lint, typecheck, production build | ✅ | — |
| Backend import, startup, `/api/health`, `/docs` | ✅ | — |
| Backend test suite (33 tests) | ✅ | — |
| Docker image builds and `docker compose up` | ✅ | — |
| Landing page and login page render | ✅ | — |
| Sign in / sign up | — | `NEXT_PUBLIC_SUPABASE_*` |
| `POST /api/agent/run` (auth) | — | `SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_*` |
| Persisting agent runs | — | `DATABASE_URL` |
| Real model responses | — | `OPENAI_API_KEY` |

Missing configuration produces explicit `503` responses with a readable message — never a fake success, and never a silent fallback to a local database.

---

## Stack and versions

| Component | Version |
| --- | --- |
| Node.js | 24 LTS (minimum 20.9, required by Next.js 16) |
| npm | 11.x |
| Python | 3.12 (3.11+ works) |
| Next.js | 16.4.3 (App Router, `src/proxy.ts` convention) |
| React | 19.3.1 |
| Tailwind CSS | 4.3.3 (CSS-first config, `@tailwindcss/postcss`) |
| TypeScript | 5.9.3 |
| FastAPI | 0.162.0 |
| SQLAlchemy | 2.1.6 |
| Pydantic / pydantic-settings | 2.14.1 / 2.16.1 |
| PyJWT | 2.15.1 |
| psycopg | 3.3.6 (`psycopg[binary]`) |
| OpenAI Python SDK | 3.40.0 |

All versions are pinned; `frontend/package-lock.json` is committed.

---

## Repository structure

```text
.
├── AGENTS.md                  # Instructions for future coding agents
├── .env.example               # Consolidated template for Docker Compose
├── docker-compose.yml         # frontend + backend services
├── backend/
│   ├── .env.example
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, lifespan, router mounting
│   │   ├── core/
│   │   │   ├── config.py      # pydantic-settings, all configuration
│   │   │   ├── database.py    # engine, SessionLocal, get_db, URL normalisation
│   │   │   └── security.py    # JWT verification (JWKS + legacy HS256)
│   │   ├── models/domain.py   # AgentTask SQLAlchemy model
│   │   ├── schemas/agent.py   # AgentRunRequest / AgentOutput / AgentRunResponse
│   │   ├── services/ai_agent.py  # OpenAI SDK wrapper, structured output
│   │   └── api/
│   │       ├── router.py
│   │       └── endpoints/{health,agent}.py
│   └── tests/                 # health, security, agent tests
└── frontend/
    ├── .env.example
    ├── Dockerfile             # multi-stage, standalone output
    ├── package.json
    ├── src/
    │   ├── proxy.ts           # Supabase SSR session refresh (Next.js 16)
    │   ├── app/{layout,page}.tsx, login/page.tsx, globals.css
    │   ├── components/{Navbar,AgentTester}.tsx
    │   └── lib/
    │       ├── api.ts         # typed fetch wrapper with bearer token
    │       ├── types.ts
    │       └── supabase/{config,client,server}.ts
```

---

## Local setup

### 1. Clone and install

**macOS / Linux**

```bash
git clone <your-repo-url> my-hackathon
cd my-hackathon

# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ..

# Frontend
cd frontend
npm ci
cd ..
```

**Windows PowerShell**

```powershell
git clone <your-repo-url> my-hackathon
cd my-hackathon

# Backend
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd ..

# Frontend
cd frontend
npm ci
cd ..
```

> If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first.

### 2. Create environment files

**macOS / Linux**

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
cp .env.example .env            # only needed for Docker Compose
```

**Windows PowerShell**

```powershell
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env.local
Copy-Item .env.example .env
```

Leave the values empty for now — everything in [What works without credentials](#what-works-without-credentials) works as-is. Fill them in later via [Configuring real integrations](#configuring-real-integrations).

---

## Running the servers

Two terminals, from the repository root.

**Backend** (`http://localhost:8000`)

```bash
cd backend
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

- Health: <http://localhost:8000/api/health>
- OpenAPI docs: <http://localhost:8000/docs>

**Frontend** (`http://localhost:3000`)

```bash
cd frontend
npm run dev
```

Open <http://localhost:3000>. You can browse the dashboard without signing in; running the agent requires a session.

---

## Checks and tests

**Backend** — 33 tests, no network access, no Supabase or AI credentials:

```bash
cd backend
source .venv/bin/activate
python -m pytest
```

Coverage includes: health without credentials, OpenAPI exposure, missing/malformed/invalid/expired/forged bearer tokens, `alg=none` rejection, HS256 legacy path, successful authenticated agent runs with persistence, prompt validation, and AI-provider failure handling.

**Frontend**:

```bash
cd frontend
npm run lint        # ESLint 9 flat config + eslint-config-next
npm run typecheck   # tsc --noEmit
npm run build       # production build (works with no env vars)
```

Optional backend lint/format (ruff is not in `requirements.txt`; install with `pip install ruff`):

```bash
cd backend
ruff check app tests
ruff format --check app tests
```

---

## Docker Compose

```bash
cp .env.example .env     # Windows: Copy-Item .env.example .env
docker compose up --build
```

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000> (health at `/api/health`)

Ports are configurable via `FRONTEND_PORT` and `BACKEND_PORT`. The backend container waits until its health check passes before the frontend starts. There is no database container: PostgreSQL is hosted by Supabase.

**`NEXT_PUBLIC_*` values are build arguments.** They are inlined into the browser bundle at build time, so after changing them you must rebuild: `docker compose build frontend --no-cache`. These values are public by definition — never put a secret in one.

Both images build and run with no credentials configured.

---

## Configuring real integrations

You need three things: a Supabase project (Auth + PostgreSQL) and an OpenAI API key.

### 1. Supabase project and keys

1. Create a project at <https://supabase.com/dashboard>.
2. Go to **Project Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL` (backend) and `NEXT_PUBLIC_SUPABASE_URL` (frontend)
   - **Publishable key** → `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` (frontend). The legacy **anon key** also works via `NEXT_PUBLIC_SUPABASE_ANON_KEY` if you have not migrated.

### 2. Auth settings

- **Email/password** is enabled by default.
- For quick testing, disable **Confirm email** under **Authentication → Providers → Email** so `signUp` returns a session immediately. If you keep it enabled, the login page shows a "check your email" notice instead of signing the user in.
- No redirect URLs are required for email/password auth.

### 3. Database connection string

Go to **Project Settings → Database → Connection string → URI** and copy it into `DATABASE_URL` (backend) or the root `.env` for Compose.

- Use the **session pooler** URI if your network does not support IPv6.
- `postgres://`, `postgresql://` and `postgresql+psycopg://` are all accepted; the app normalises them to the psycopg v3 driver.
- **URL-encode special characters in the password.** For example `p@ssw0rd!` becomes `p%40ssw0rd%21`. An unencoded `@` or `#` is the most common cause of "invalid connection string".
- Add `?sslmode=require` if your connection string does not already include SSL parameters. Unknown query parameters are stripped automatically.

### 4. JWT verification (how auth actually works)

Supabase access tokens are verified in `backend/app/core/security.py`:

- **Default: asymmetric signing keys.** The backend fetches the project's public keys from `https://<project-ref>.supabase.co/auth/v1/.well-known/jwks.json` (derived from `SUPABASE_URL`, or set `SUPABASE_JWKS_URL` explicitly). Keys are cached, not fetched per request. Only `ES256/384/512` and `RS256/384/512` are accepted; `alg=none` and algorithm confusion are rejected.
- **Legacy: HS256 shared secret.** `SUPABASE_JWT_SECRET` is used *only* when a token's header says `HS256` and the variable is explicitly set. New projects should leave it empty. If you set it, use the JWT secret from **Project Settings → API → JWT Settings**.

Every token must also pass issuer (`$SUPABASE_URL/auth/v1`), audience (`authenticated` by default), expiry, and a non-empty `sub` claim. Never trust an unverified payload — there is no code path that does.

### 5. AI provider

Create a key at <https://platform.openai.com/api-keys> and set `OPENAI_API_KEY` in `backend/.env` (or the root `.env` for Compose). `OPENAI_MODEL` defaults to `gpt-4.1-mini`.

The service (`backend/app/services/ai_agent.py`) calls the Responses API with `text_format=AgentOutput`, so the model's reply is parsed and validated against the Pydantic schema. Missing key → `503`; provider failure → `502`; refusal → `422`. Provider error details and stack traces are never returned to the client.

### 6. Restart

Restart the backend after changing `backend/.env`, and the frontend after changing `frontend/.env.local` (Next.js reads public env vars at build/start time).

---

## Troubleshooting

**`503 DATABASE_URL is not configured`** — `backend/.env` is missing or empty. Copy the example and paste the Supabase URI.

**`503 Authentication is not configured on the server`** — the token uses an asymmetric algorithm but `SUPABASE_URL` / `SUPABASE_JWKS_URL` is unset. Set the project URL.

**`401 Invalid authentication token`** — the frontend and backend point at different Supabase projects, the token expired, or the user never signed in. Check that `NEXT_PUBLIC_SUPABASE_URL` and `SUPABASE_URL` match.

**`503 Authentication service is temporarily unavailable`** — the backend could not reach the JWKS endpoint. Check network access to `*.supabase.co`.

**Database connection errors / `invalid connection string`** — the password contains unencoded special characters (`@`, `#`, `:`, `/`). URL-encode them. Also confirm you copied the URI (not the "Direct connection" host/port pair) and that `sslmode` is set.

**CORS errors in the browser** — the frontend origin must be listed in `CORS_ORIGINS` on the backend, e.g. `CORS_ORIGINS=["http://localhost:3000"]`. A JSON array or comma separated list both work. Restart the backend after changing it.

**`Could not reach the backend API`** — the backend is not running, or `NEXT_PUBLIC_API_URL` is wrong. It must include the `/api` suffix: `http://localhost:8000/api`. In Docker, it must be the URL the *browser* uses (`http://localhost:8000/api`), not the Compose service name.

**Sign-up succeeds but the user is not signed in** — Supabase email confirmation is enabled. Either confirm the email, or disable **Confirm email** in the Supabase dashboard.

**Signed out at random / session never refreshes** — `src/proxy.ts` is not running. On Next.js 16 the file must be named `proxy.ts` (inside `src/`), not `middleware.ts`.

**Tables do not exist** — `AUTO_CREATE_TABLES=true` creates them on backend startup when `DATABASE_URL` is set. It is a development convenience only; use real migrations (e.g. Alembic) in production.

**`NEXT_PUBLIC_` changes are ignored in Docker** — they are baked in at build time. Rebuild with `docker compose build frontend --no-cache`.

---

## Notes and limitations

- Automatic table creation (`Base.metadata.create_all`) is a hackathon convenience, not a migration strategy.
- The agent is a single structured-output call. `TOOL_DEFINITIONS` in `services/ai_agent.py` is an intentionally empty placeholder for future tools; nothing pretends to be implemented.
- The Next.js proxy refreshes sessions but is not the authorization boundary — FastAPI verifies every token itself.
- No LangGraph, Celery, Redis, pgvector or Kubernetes. Add infrastructure only when a concrete feature requires it.
