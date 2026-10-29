# Overdraft Guard

An AI agent that warns bank clients **before** their current account goes negative, compares every
way to cover the gap, and fixes it in one tap.

## ▶ [Try it live](https://nexxt-ai-project-1.onrender.com)

**[nexxt-ai-project-1.onrender.com](https://nexxt-ai-project-1.onrender.com)**: log in as
`andrei` / `overdraft2026` (or any [demo account](#demo-accounts-password-overdraft2026)).
API documentation: [nexxt-ai-project.onrender.com/docs](https://nexxt-ai-project.onrender.com/docs)

> Free Render instances sleep when idle: the first visit can take about a minute.

## The problem

Clients rarely lack money: it is **in the wrong account on the wrong day**. A bill hits an empty
current account and the client pays overdraft fees while their savings sit at the same bank.
Only 22% of Romanian adults are financially literate (S&P Global FinLit Survey, 2014), the lowest
in the EU, so few people plan which account pays which bill.

## What makes it different

- It moves money **between the client's own accounts** instead of telling them to spend less.
- It acts **before** the bill, not after the fee.
- The AI **explains, it never calculates**: every amount comes from a deterministic engine, so the
  advice is exact and repeatable.
- It is honest when there is nothing cheaper: no risk means no alert, no money anywhere means
  "the overdraft is your only option".

## How it works

1. **Engine (no AI):** forecasts the current-account balance day by day until payday, finds the
   overdraft, and prices each option: do nothing (fee + daily interest), use savings (interest lost)
   or pay the bill by card (free inside the grace period).
2. **AI:** Claude turns the result into a headline and bullet points. It never sees transactions
   and never calculates.
3. **Check:** if the AI names another option or a number not in the result, or is unavailable, the
   app shows its own pre-written explanation. The answer is always correct.
4. **Apply:** the client approves in a simulated banking-app pop-up; the change is saved in their
   own database.

## The banking domain

**Data per client:** accounts (current, credit card, savings), one month of transactions with
merchant category codes, scheduled payments (bills, salary) and product terms (overdraft rate and
fee, savings interest, card grace period).

**Rules the engine follows** (reasons in `DECISIONS.md`):

- **Overdraft:** a 30.00 RON fee plus interest on **each day's** negative balance, not on the lowest point.
- **Savings:** withdrawing early forfeits the interest accrued so far.
- **Credit card:** free if repaid from the salary inside the grace period, interest after it.
- **Same day:** a salary and a bill on the same day net out.
- **Fair comparison:** each option is priced as if it were the only action taken.
- **Exact money:** decimal arithmetic, rounded once at the end.

**Exceptions it handles:**

- Transfers between the client's own accounts are not counted as income or spending.
- Bills paid from another account (e.g. Spotify on the card) do not affect the current account.
- No scheduled bills: they are inferred from last month's recurring payments (same merchant,
  stable amount).
- Variable bills (e.g. Enel) use the issued invoice amount; before the invoice exists, that is a
  known limitation (see below).

**Out of scope on purpose:** advice on past spending or future budgets. The agent solves the
bill that is coming.

## Agent design

- **One agent, on purpose.** The task is "explain a decision clearly". More agents would not make
  the maths more reliable.
- **Tools, not free text:** the engine's steps (categorise → detect recurring → forecast → price →
  rank) produce one decision. The AI receives only that decision and must answer through a single
  structured "submit recommendation" tool.
- **Checked output:** the answer is rejected if the option differs from the engine's, the status
  is wrong, or any amount is not in the decision.
- **Unexpected situations:** AI down, a 20-second timeout, expired credentials or a refusal all
  fall back to the pre-written explanation; the page never breaks.
- **Payment safety:** a payment needs an approved confirmation that belongs to the client, works
  once and expires after 120 seconds.

## Demo accounts (password `overdraft2026`)

| User | Situation | Agent recommends |
| --- | --- | --- |
| `andrei` | Utility bill empties the account | Pay by card (0.00 RON vs 31.19 overdraft) |
| `maria` | Enough money | No action needed |
| `ioana` | No credit card | Use savings (12.40 RON) |
| `mihai` | Card grace period too short | Savings (1.50) beat the card (2.03) |
| `elena` | No money anywhere | Overdraft is the only option |
| `radu` | No scheduled bills | Bills inferred from last month |

Each client has their **own PostgreSQL database**. "Reset my demo data" restores the original.

## Core scenario to check (Andrei)

1. Log in as `andrei`: overdraft on **5 Nov**, lowest point **−318.40 RON**, 5 days negative.
2. Options: do nothing **31.19**, use savings **12.40**, pay the Enel bill by card **0.00** (recommended).
3. Apply → approve in the pop-up (3 seconds) → "Payment successful"; card 8,150.00 → 7,531.60.
4. Log out and back in: still paid. "Reset my demo data" brings the overdraft back.

## Verify it's calculated, not hardcoded

Every page load reads the client's database and runs the engine again:

- **Other users:** the same code gives six different decisions.
- **By hand:** "How the engine computed this" shows each formula, e.g.
  (4 × 168.40 + 318.40) × 0.0012 = 1.19, plus the 30.00 fee = **31.19**.
- **Refresh:** the AI's wording changes, the numbers stay identical.
- **Change the data** (locally), then refresh the page:

```bash
docker compose exec db psql -U bank -d client_andrei -c \
  "update accounts set available_balance = 600 where account_id = 'ACC-DEBIT-001'"
```

| Andrei's balance | Lowest point | Overdraft cost | Recommendation |
| --- | --- | --- | --- |
| 450.00 (demo) | −318.40 | 31.19 | Pay by card |
| 600.00 | −168.40 | 30.29 | Pay by card |
| 800.00 | +31.60 | — | No action needed |

**77 automated tests** check hand-computed values, every demo user, login and isolation between
clients, payment confirmation, and AI failures: `cd backend && python -m pytest` (no database or
AI needed).

## Architecture

```
Browser (Next.js) ──► FastAPI ──► login database: who you are
                         │
                         ├──► your own database ──► engine ──► decision
                         │                                        │
                         │                       AI (Claude) ◄────┘ explanation, then checked
                         └──► confirmation ──► change saved in your database
```

| Part | Technology |
| --- | --- |
| Frontend | Next.js 16, React 19, Tailwind (`frontend/`) |
| Backend | FastAPI, SQLAlchemy (`backend/`) |
| Engine | Plain Python, no AI (`backend/app/services/banking/`) |
| AI | Claude on Amazon Bedrock (`backend/app/services/ai_agent.py`) |
| Data | PostgreSQL: one login database + one database per client, seeded from `backend/app/data/users/` |
| Login | Hashed passwords, signed session tokens; each request only opens the logged-in client's database |
| Hosting | Render: two web services + PostgreSQL |

More detail: `PLAN.md` (what and why), `DECISIONS.md` (choices), `AGENTS.md` (code rules).

## Run it yourself

```bash
cp .env.example .env          # optional: add AWS credentials for the AI wording
docker compose up --build     # PostgreSQL + backend + frontend, databases seeded automatically
```

Open <http://localhost:3000>. Without AWS credentials everything works; the explanation then uses
the built-in wording. Re-seed all clients: `cd backend && python -m app.seed --reset`.

## Limitations and next steps

- Fictional clients with one month of history; not tested on real bank data.
- Transfers are simulated; demo-grade login (no rate limiting or password reset).
- Variable bills before the invoice (e.g. Enel): next step is forecasting a range and covering the
  top of it.
- Next: push alerts in the banking app, and exposing the engine to the bank's other assistants.
- The overdraft statistics in the pitch are estimates; the real figures need bank data.
