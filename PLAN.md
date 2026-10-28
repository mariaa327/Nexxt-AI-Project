# PLAN — Proactive Overdraft Agent

## Problem

Clients rarely lack money. They hold it across several products (current account, savings,
credit card) and do not synchronise their cash flow. Automatic bills and recurring payments hit
an empty current account, the account goes negative, and the client pays penalty overdraft
interest while thousands of lei sit in a savings account at the same bank.

The cause is fragmentation plus weak financial education, not poverty.

## Solution

An agent that **anticipates** the next bills, detects the overdraft before it happens, prices
every way of covering the gap, and recommends the cheapest one in plain language. The client
confirms with one click and the app executes it (simulated in this version).

## Scope of this version

In scope:

1. **Deterministic engine (backend)** — load the client data, categorise transactions, detect
   recurring obligations, project the current-account balance day by day, find the shortfall,
   and price each coverage option exactly.
2. **LLM as translator only** — receives the precomputed decision JSON, never raw transactions,
   and phrases it as bullet points. It does no arithmetic.
3. **Dashboard UI** — balances, upcoming bills, projected-balance chart, recommendation, one-click
   apply, and a dropdown explaining how the engine computed the numbers.
4. **No authentication** — Supabase Auth is removed; the app serves one demo client.

Out of scope:

- Analysing past spending trends to advise how to avoid the situation next month. Spending is
  categorised only to describe the current situation; there is no budgeting advice.
- Real banking integration. Execution changes in-memory state.

## Architecture

```
browser ──► Next.js dashboard (/)
              │  GET  /api/dashboard        deterministic, no LLM
              │  POST /api/agent/analyze    engine → LLM (or rules fallback)
              │  POST /api/agent/execute    apply option in memory
              ▼
FastAPI ──► services/banking/
              loader → categorizer → recurring → projection → options → engine
            services/ai_agent.py   BillDecision → AgentRecommendation
            services/persistence.py  best-effort row in agent_tasks
```

The LLM sees only `BillDecision`. If its answer names an option the engine did not recommend, or
no API key is configured, a deterministic rules message is returned instead
(`generated_by: "rules"`).

## Demo scenario

Data: `backend/app/data/client1_date.json` (the original October history, plus a savings
account, product parameters and scheduled November payments). Today is `2026-10-28`.

| Account | Balance |
| --- | --- |
| Current `ACC-DEBIT-001` | 450,00 |
| Credit card `ACC-CREDIT-002` | 8.150,00 available of 10.000,00 |
| Savings `ACC-SAVINGS-003` | 12.000,00, accrued interest 12,40 |

| Date | Event | Current-account balance |
| --- | --- | --- |
| 2026-10-28 | opening | 450,00 |
| 2026-11-05 | Enel regularisation −618,40 | **−168,40** (first deficit) |
| 2026-11-09 | World Class −150,00 | **−318,40** (peak) |
| 2026-11-10 | salary +9.500,00, rent −2.200,00 | 6.981,60 |

Options, each priced as if it were the only action taken:

| Option | Cost | How |
| --- | --- | --- |
| Do nothing (overdraft) | 31,19 | 30,00 fee + Σ daily deficit × 0,0012 = 30,00 + 992,00 × 0,0012 |
| Withdraw from savings | 12,40 | accrued interest forfeited |
| **Pay the bill from the credit card** | **0,00** | repaid at salary, 5 days < 30-day grace period |

Recommendation: pay the Enel bill from the credit card.

## Order of work

See `PROGRESS.md` for the live checklist.

## Verification

- `cd backend && ../.venv/bin/python -m pytest -q` — no Supabase or AI credentials needed.
- `cd frontend && npm run lint && npm run typecheck && npm run build`.
- `docker compose config`; `docker compose up --build` when Docker is available.
- Without `OPENAI_API_KEY`: dashboard works, `analyze` returns `generated_by: "rules"`.
- Without `DATABASE_URL`: `analyze` returns `persisted: false` and nothing fails.
