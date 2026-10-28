import { CheckCircle2, Loader2, ShieldAlert, Sparkles } from "lucide-react";

import { formatDay, formatRon } from "@/lib/format";
import type { AgentRecommendation, BillDecision, CostOption, OptionId } from "@/lib/types";

type Props = {
  decision: BillDecision;
  recommendation: AgentRecommendation | null;
  recommendationError: string | null;
  applying: boolean;
  onApply: (optionId: OptionId) => void;
};

export function RecommendationCard({
  decision,
  recommendation,
  recommendationError,
  applying,
  onApply,
}: Props) {
  const recommended = decision.options.find(
    (o) => o.option_id === decision.recommended_option_id,
  );
  const noRisk = decision.no_action_needed;

  return (
    <section
      aria-labelledby="recommendation-heading"
      className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm sm:p-6"
    >
      <div className="flex items-start gap-3">
        <span
          className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
            noRisk
              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
              : "bg-[var(--accent)]/10 text-[var(--accent)]"
          }`}
        >
          {noRisk ? (
            <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
          ) : (
            <Sparkles aria-hidden="true" className="h-4 w-4" />
          )}
        </span>
        <div className="min-w-0">
          <h2 id="recommendation-heading" className="text-lg font-semibold">
            {noRisk ? "You are covered" : "Recommendation"}
          </h2>
          <div aria-live="polite">
            {recommendation ? (
              <p className="mt-1 text-sm">{recommendation.headline}</p>
            ) : recommendationError ? (
              <p role="alert" className="mt-1 text-sm text-red-600 dark:text-red-400">
                {recommendationError}
              </p>
            ) : (
              <p className="mt-1 flex items-center gap-2 text-sm text-[var(--muted)]">
                <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                Preparing your recommendation…
              </p>
            )}
          </div>
        </div>
      </div>

      {recommendation && (
        <div className="mt-5 space-y-4">
          <div>
            <h3 className="text-sm font-semibold">Why</h3>
            <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm">
              {recommendation.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          </div>

          {recommendation.trade_offs.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold">Alternatives considered</h3>
              <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-[var(--muted)]">
                {recommendation.trade_offs.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          )}

          {recommended && recommended.option_id !== "overdraft" && (
            <button
              type="button"
              onClick={() => onApply(recommended.option_id)}
              disabled={applying}
              className="inline-flex items-center gap-2 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {applying ? (
                <>
                  <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
                  Verifying…
                </>
              ) : (
                <>
                  <ShieldAlert aria-hidden="true" className="h-4 w-4" />
                  Apply: {recommended.label.toLowerCase()}
                </>
              )}
            </button>
          )}
        </div>
      )}

      <EngineDetails decision={decision} recommendation={recommendation} />
    </section>
  );
}

function EngineDetails({
  decision,
  recommendation,
}: {
  decision: BillDecision;
  recommendation: AgentRecommendation | null;
}) {
  const p = decision.projection;
  return (
    <details className="mt-6 rounded-lg border border-[var(--border)] bg-[var(--background)] p-4 text-sm">
      <summary className="cursor-pointer font-medium">How the engine computed this</summary>
      <div className="mt-3 space-y-4">
        <p className="text-[var(--muted)]">
          Every number is calculated by a deterministic engine from your accounts and
          scheduled payments. The AI only receives this result and puts it into words; it
          does not see your transactions and does no arithmetic.
        </p>

        <dl className="grid grid-cols-2 gap-x-4 gap-y-1 tabular-nums sm:grid-cols-4">
          <Fact label="First negative day" value={p.first_deficit_date ? formatDay(p.first_deficit_date) : "None"} />
          <Fact label="Lowest balance" value={formatRon(p.lowest_balance)} />
          <Fact label="Days negative" value={String(p.deficit_days)} />
          <Fact label="Next income" value={p.next_income_date ? formatDay(p.next_income_date) : "None"} />
        </dl>

        {decision.options.length > 0 && (
          <ol className="space-y-3">
            {decision.options.map((option, index) => (
              <OptionRow key={option.option_id} option={option} rank={index + 1} />
            ))}
          </ol>
        )}

        <p className="text-xs text-[var(--muted)]">
          Payments source:{" "}
          {decision.payments_source === "scheduled"
            ? "scheduled payments"
            : "inferred from last month's recurring payments"}
          .{" "}
          {recommendation &&
            (recommendation.generated_by === "llm"
              ? "Wording: AI model, checked against the engine's numbers."
              : `Wording: built-in rules (${recommendation.fallback_reason ?? "fallback"}).`)}
        </p>
      </div>
    </details>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-[var(--muted)]">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}

function OptionRow({ option, rank }: { option: CostOption; rank: number }) {
  return (
    <li className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-medium">
          {rank}. {option.label}
        </span>
        <span className="font-semibold tabular-nums">{formatRon(option.cost)}</span>
      </div>
      <p className="mt-1 font-mono text-xs text-[var(--muted)]">{option.formula}</p>
      <ul className="mt-1 list-disc pl-5 text-xs text-[var(--muted)]">
        {option.assumptions.map((a) => (
          <li key={a}>{a}</li>
        ))}
        {!option.feasible && <li>Not enough funds to do this in full.</li>}
      </ul>
    </li>
  );
}
