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

## D3 — Supabase authentication removed

**Decision:** no login, no JWT verification, no session proxy. The backend serves one demo client.

**Why:** authentication is not what this hackathon presents, and it is a failure point during a
live demo.

**Consequence:** the app must not be deployed with real client data as-is.

## D4 — Persistence is best-effort

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

## D6 — The demo data is extended

**Decision:** `client1_date.json` moves to `backend/app/data/` and gains a savings account,
`product_parameters` and `scheduled_payments`; the current balance is lowered to 450,00.

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

## D11 — Demo reset endpoint

**Decision:** `POST /api/agent/reset` reloads the data file into memory.

**Why:** executing an option changes the demo state; the scenario has to be repeatable on stage.
