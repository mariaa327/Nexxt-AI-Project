# Overdraft Guard

An AI agent that sees your next bills coming, finds the day your current account would go
negative, and picks the cheapest way to cover it — before you pay a single leu of overdraft
interest.

## The problem

Most people who hit an overdraft are not short of money. Their money is **fragmented**: a
current account that pays the bills, a savings account, a credit card. Nobody synchronises
them, and there is little financial education on how to prioritise. So an automatic bill hits
an empty current account, the account goes negative, and the client pays penalty interest —
while thousands of lei sit in savings at the same bank.

## What the agent does

1. **Looks ahead.** Projects the current-account balance day by day until the next salary,
   using scheduled payments (or, if none are known, the recurring payments found in last
   month's history).
2. **Spots the gap.** Finds the first negative day, how deep it goes and for how long.
3. **Prices every way out**, each as if it were the only action taken:
   - do nothing → overdraft fee + interest on each day's negative balance;
   - withdraw from savings → the accrued interest you forfeit;
   - pay the bill with the credit card → zero if your salary repays it inside the grace period.
4. **Explains it in plain words** — a headline and bullet points — and executes the chosen
   option after a simulated banking-app approval (3-D-Secure-style pop-up).

### Example: Andrei (`backend/app/data/users/andrei.json`, today = 28 Oct 2026)

| | |
| --- | --- |
| Current account | 450.00 RON |
| Credit card | 8,150.00 RON available |
| Savings | 12,000.00 RON, 12.40 RON accrued interest |
| 5 Nov | Enel regularisation −618.40 → balance **−168.40** |
| 9 Nov | World Class −150.00 → **−318.40** |
| 10 Nov | Salary +9,500.00, rent −2,200.00 → 6,981.60 |

| Option | Cost |
| --- | --- |
| Do nothing | 31.19 RON (30.00 fee + 992.00 × 0.0012) |
| Withdraw from savings | 12.40 RON |
| **Pay Enel with the credit card** | **0.00 RON** ← recommended |

## Demo accounts

Each fictional client has their own PostgreSQL database and shows one edge case. Password for all:
`overdraft2026` (also shown on the login page).

| Username | Client | Situation | The agent recommends |
| --- | --- | --- | --- |
| `andrei` | Andrei Popescu | A utility bill empties the current account | Pay it with the credit card (0.00 RON) |
| `maria` | Maria Ionescu | Enough money in the current account | No action needed |
| `ioana` | Ioana Dumitrescu | No credit card | Withdraw from savings (12.40 RON) |
| `mihai` | Mihai Stan | Card grace period only 3 days | Savings (1.50) beat the card (2.03) |
| `elena` | Elena Radu | Not enough money in any account | Overdraft is the only option (31.19) |
| `radu` | Radu Marin | No scheduled bills | Bills inferred from last month; pay with the card |

Applying an option is saved in that client's database: log out and in again and it is still
there. "Reset my demo data" restores the original situation.

## How precision is guaranteed

The LLM never does arithmetic. A deterministic engine (`backend/app/services/banking/`)
categorises transactions, detects recurring payments, projects the balance and prices the
options. The model receives only that computed decision — never the raw transactions — and
turns it into a recommendation. Its output is checked: if it recommends a different option or
quotes an amount that is not in the decision, the built-in rules wording is used instead.

Without AWS credentials the whole demo still works; the recommendation is then worded by
the rules. See `DECISIONS.md` for the reasoning behind each choice.

## Run it

Nothing needs configuring. From the repository root:

```bash
docker compose up --build
```

This starts PostgreSQL, creates `bank_directory` plus one `client_<username>` database per demo
user, and seeds them. Open <http://localhost:3000> and log in (API at
<http://localhost:8000/docs>).

For development, run only the database in Docker and the rest locally:

```bash
docker compose up -d db

# Backend (creates and seeds the databases on startup)
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# Re-seed every user from scratch
cd backend && python -m app.seed --reset

# Frontend
cd frontend && npm ci && npm run dev
```

Optional configuration (copy `.env.example` → `.env` for Docker, or `backend/.env.example` →
`backend/.env`):

| Variable | Effect |
| --- | --- |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_DEFAULT_REGION` | Claude on Amazon Bedrock phrases the recommendation instead of the rules. |
| `BEDROCK_MODEL_ID` | Bedrock model (default `us.anthropic.claude-sonnet-5-5`). |
| `DATABASE_ADMIN_URL` | PostgreSQL server connection allowed to create databases (default `postgresql://bank:bank@localhost:5432/postgres`). |
| `SESSION_SECRET` | Signs login tokens; set it to stay logged in across backend restarts. |
| `DEMO_TODAY` | Changes "today" for the projection. |
| `DEMO_APPROVAL_SECONDS` | Delay before the simulated app approval (default 3). |
| `AI_TIMEOUT_SECONDS` | Provider timeout before falling back to rules wording (default 20). |
| `NEXT_PUBLIC_API_URL` | Backend URL as seen by the browser (default `http://localhost:8000/api`). |

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness, database reachable, AI configured |
| `POST` | `/api/auth/login` | `{"username", "password"}` → session token |
| `GET` | `/api/auth/me` | The logged-in user |
| `GET` | `/api/auth/demo-users` | Demo accounts for the login page |
| `GET` | `/api/dashboard` | The logged-in user's balances, upcoming payments, projection, priced options |
| `POST` | `/api/agent/analyze` | Decision + worded recommendation |
| `POST` | `/api/agent/execute/initiate` | Start verification for an option (`{"option_id": "credit_card"}`) |
| `GET` | `/api/agent/challenges/{id}` | Verification status: `pending` → `approved` after 3 s |
| `POST` | `/api/agent/challenges/{id}/cancel` | Cancel a verification |
| `POST` | `/api/agent/execute` | Apply an approved option (`{"challenge_id": "…"}`), saved to the user's database |
| `POST` | `/api/agent/reset` | Restore the logged-in user's seed data |

Everything except `health`, `login` and `demo-users` needs `Authorization: Bearer <token>`.

## Checks

```bash
cd backend && python -m pytest          # no PostgreSQL or AWS needed (SQLite per user)
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Limits

- Demo authentication only (no rate limiting, password reset or token revocation); fictional data.
- Transfers are simulated: balances change in the client's database, no real bank is contacted.
- Out of scope for this version: analysing spending trends to advise on future budgeting.
