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
   option with one click (simulated).

### Demo scenario (`backend/app/data/client1_date.json`, today = 28 Oct 2026)

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

## How precision is guaranteed

The LLM never does arithmetic. A deterministic engine (`backend/app/services/banking/`)
categorises transactions, detects recurring payments, projects the balance and prices the
options. The model receives only that computed decision — never the raw transactions — and
turns it into a recommendation. Its output is checked: if it recommends a different option or
quotes an amount that is not in the decision, the built-in rules wording is used instead.

Without an `OPENAI_API_KEY` the whole demo still works; the recommendation is then worded by
the rules. See `DECISIONS.md` for the reasoning behind each choice.

## Run it

Nothing needs configuring. From the repository root:

```bash
docker compose up --build
```

Then open <http://localhost:3000> (API at <http://localhost:8000/docs>).

Without Docker, in two terminals:

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm ci && npm run dev
```

Optional configuration (copy `.env.example` → `.env` for Docker, or `backend/.env.example` →
`backend/.env`):

| Variable | Effect |
| --- | --- |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | The model phrases the recommendation instead of the rules. |
| `DATABASE_URL` | Each analysis is stored in `agent_tasks`. |
| `DEMO_TODAY` | Changes "today" for the projection. |
| `NEXT_PUBLIC_API_URL` | Backend URL as seen by the browser (default `http://localhost:8000/api`). |

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness and which integrations are configured |
| `GET` | `/api/dashboard` | Balances, upcoming payments, projection, priced options |
| `POST` | `/api/agent/analyze` | Decision + worded recommendation |
| `POST` | `/api/agent/execute` | Apply an option (`{"option_id": "credit_card"}`), simulated |
| `POST` | `/api/agent/reset` | Restore the original demo data |

## Checks

```bash
cd backend && python -m pytest          # no credentials needed
cd frontend && npm run lint && npm run typecheck && npm run build
```

## Limits

- Single demo client, no authentication: do not load real client data as-is.
- Transfers are simulated in memory and reset on restart.
- Out of scope for this version: analysing spending trends to advise on future budgeting.
