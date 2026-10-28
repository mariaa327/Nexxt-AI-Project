# DECISIONS

Short records of choices that are not obvious from the code. Newest last.

## D1 — The engine computes, the LLM only phrases

**Decision:** all arithmetic (projection, overdraft interest, option costs, ranking) runs in
deterministic Python. The LLM receives the finished `BillDecision` JSON and turns it into bullet
points.

**Why:** with dozens of transactions and several account types an LLM confuses accounts and makes
arithmetic mistakes. Example caught while planning: pricing the overdraft as `peak × days` gives
31,91 instead of the correct 31,19, because the deficit is smaller on the first four days.

**Consequence:** the model's output is checked; if it names a different option than the engine,
the rules-based message is used instead.

## D2 — Raw transactions never reach the model

**Decision:** only the computed decision is sent to the LLM.

**Why:** smaller prompt, no hallucinated figures, and no personal transaction detail sent to the
provider beyond what the explanation needs.

## D3 — Supabase authentication removed *(superseded by D17/D18: demo login)*

**Decision:** no login, no JWT verification, no session proxy. The backend serves one demo client.

**Why:** authentication is not what this hackathon presents, and it is a failure point during a
live demo.

**Consequence:** the app must not be deployed with real client data as-is.

## D4 — Persistence is best-effort *(superseded by D17: each user's database is required)*

**Decision:** analyses are still written to `agent_tasks` when `DATABASE_URL` is set. When it is
unset or the database fails, the response says `persisted: false` and the request still succeeds.

**Why:** the product is the recommendation, not the stored row. The starter template returned
503 before even calling the agent when the database was missing.

**Consequence:** deviates from the starter's "database required" posture. `agent_tasks.user_id`
became `customer_id`; an existing dev table must be dropped once (no migrations).

## D5 — Money is `Decimal`, rounded once

**Decision:** amounts are parsed with `Decimal(str(x))`, kept unrounded through calculations, and
rounded to 2 decimals (`ROUND_HALF_UP`) only at the end.

**Why:** rounding inside the daily-interest loop shifts results by cents and breaks exact tests.

## D6 — The demo data is extended *(now the seed of user `andrei`, D17)*

**Decision:** the app reads an extended copy at `backend/app/data/client1_date.json`, which adds a
savings account, `product_parameters` and `scheduled_payments` and lowers the current balance to
450,00. The original `client1_date.json` at the repository root stays as the team's source data
(committed in `0470baa`) and is not read by the app.

**Why:** the original file never produces an overdraft (2.845,50 RON balance, no savings account,
no rates), so the product could not be demonstrated. The October transactions are unchanged.
The fixture lives under `app/` because the backend Docker image copies only `app/`.

The deficit comes from an Enel regularisation (annual true-up) — the ordinary monthly bills
alone never empty the account because rent leaves on payday.

## D7 — Each option is priced independently

**Decision:** every option is costed as if it were the only action taken.

**Why:** stacking costs (e.g. savings withdrawal on top of overdraft) would double-count and make
the comparison meaningless.

## D8 — Spotify stays on the credit card

**Decision:** Spotify is not in the current-account projection.

**Why:** the October history bills it to `ACC-CREDIT-002`. It is itself an example of the
fragmentation the product addresses.

## D9 — English UI, bullet-point recommendation, engine on demand

**Decision:** the UI and the recommendation are in English. The recommendation is a headline plus
bullet points of the decisions made; the engine's costs and formulas sit in a separate collapsed
dropdown.

**Why:** chosen by the team for the jury audience; keeps the main flow simple while the maths
stays inspectable.

## D10 — AI failures never block the recommendation

**Decision:** a missing key, provider error, refusal, or a draft that fails the consistency check
(different option, unknown amount, wrong status) all return the rules wording with
`generated_by: "rules"` and a `fallback_reason`, instead of an HTTP error.

**Why:** the numbers come from the engine anyway; only the wording is at stake, and a live demo
must not fail because a provider is down. The dropdown in the UI shows which wording was used.

## D11 — Demo reset endpoint *(now resets the logged-in user's database)*

**Decision:** `POST /api/agent/reset` reloads the data file into memory.

**Why:** executing an option changes the demo state; the scenario has to be repeatable on stage.

## D12 — Payment verification is a backend challenge (simulated app approval)

**Decision:** applying an option takes two steps. `POST /api/agent/execute/initiate` creates a
challenge, which is approved automatically after `DEMO_APPROVAL_SECONDS` (default 3), simulating
approval in the banking app. `POST /api/agent/execute` only accepts an approved, unused, unexpired
challenge (120 s). The frontend shows a 3-D-Secure-style modal while polling.

**Why:** the flow looks like a real bank confirmation, and the API cannot move money without it,
which is tested. No real SMS, app or bank is involved.

## D13 — Mobile-first dashboard

**Decision:** no text hero. The first screen is the alert ("Overdraft on 5 Nov unless you act")
with the projection chart, then the recommendation; balances and payments come after. The chart
lays out in real pixels for its container so labels stay readable on phones.

**Why:** on a phone the first thing a client should see is the problem and the fix.

## D14 — Provider timeout

**Decision:** OpenAI calls time out after `OPENAI_TIMEOUT_SECONDS` (default 20) with one retry.

**Why:** the SDK default is 600 s; a hung provider would freeze the recommendation. On timeout
the rules wording is shown (D10).

## D15 — AI provider is Amazon Bedrock (Claude), not OpenAI

**Decision:** the recommendation is worded by Claude on Amazon Bedrock (Converse API,
`BEDROCK_MODEL_ID`, default `us.anthropic.claude-sonnet-5-5`), using the hackathon's AWS
credentials. The model answers through one tool whose input schema is `RecommendationDraft`; the
tool choice is `auto` because current Claude models on Bedrock reject a forced tool choice. A
reply without the tool call falls back to rules (D10).

**Why:** the hackathon provides AWS credentials, not an OpenAI key. The architecture is
unchanged: only `services/ai_agent.py` and its settings changed. Verified live: 6/6 scenarios
returned model wording that passed the consistency check, in 5–8 s.

**Consequence:** the credentials are temporary (session token). When they expire the app keeps
working with rules wording; refresh all three `AWS_*` values in `.env` / `backend/.env` and
restart the backend. Credentials live only in gitignored `.env` files, never in `.env.example`.

## D16 — Dynamic data: bundled scenarios plus upload *(superseded by D17: one user per edge case)*

**Decision:** `backend/app/data/scenarios/*.json` holds one file per edge case (covered, no credit
card, short grace period, insufficient funds, no scheduled payments), each the team's October
history with only the parameters that create that case changed. `POST /api/scenarios/{id}` loads
one; `POST /api/scenarios/upload` accepts any client JSON in the same format, validated by the
same loader. Reset returns to the loaded data. The UI has a dropdown and an "Upload JSON" button.

**Why:** shows that every number, the recommendation and the applied change are computed from the
data, not scripted for one client, and lets the jury try their own file.

## D17 — Fictional users, each with their own PostgreSQL database

**Decision:** each edge case is a fictional client (`andrei`, `maria`, `ioana`, `mihai`, `elena`,
`radu`) with an individual PostgreSQL database `client_<username>` (accounts, transactions,
scheduled payments, product terms, analyses). A separate `bank_directory` database holds only the
logins and which database belongs to whom. On startup the backend creates and seeds any missing
database from `backend/app/data/users/<username>.json` (idempotent; `python -m app.seed --reset`
re-seeds everything). Applying an option is saved to the user's database; "Reset my demo data"
re-seeds it. The scenario dropdown and JSON upload are removed.

**Why:** the app is client-facing: you log in and see your own bank data. Separate databases make
the isolation between clients physical, not just a `WHERE` clause, and show the data is real and
dynamic, not scripted.

**Consequence:** PostgreSQL is now required (`docker compose up -d db` for local development).
Tests use an in-memory SQLite database per user and need neither PostgreSQL nor AWS. Seeding
caught a data bug: the "no credit card" client still had card transactions; they were removed.
The engine is unchanged: the repository loads a user's database into the same `ClientSnapshot`.

## D18 — Login with standard-library session tokens

**Decision:** username + password; passwords stored as salted scrypt hashes; the session token is
`user_id.expiry.HMAC-SHA256` signed with `SESSION_SECRET` (8 h). Every data endpoint resolves the
user from the token and opens a session on that user's database only. Wrong username and wrong
password return the same 401. Payment confirmations belong to the user who started them. All demo
users share the password `overdraft2026`, shown on the login page for the jury.

**Why:** real enough for the demo (no plaintext passwords, tamper-proof tokens, per-user
isolation) without new dependencies or an external auth service. The frontend keeps the token in
`sessionStorage`.

**Consequence:** not production auth: no rate limiting, no password reset, no token revocation.
Without `SESSION_SECRET` a random key is used and a backend restart logs everyone out.
