"use client";

import { AlertCircle, CalendarClock, Loader2, RotateCcw, TrendingDown } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BeforeAfter } from "@/components/BeforeAfter";
import { Balances } from "@/components/Balances";
import { ProjectionChart } from "@/components/ProjectionChart";
import { RecommendationCard } from "@/components/RecommendationCard";
import { UpcomingBills } from "@/components/UpcomingBills";
import { analyze, ApiError, executeOption, getDashboard, resetDemo } from "@/lib/api";
import { formatLongDay } from "@/lib/format";
import type { AgentRecommendation, BillDecision, ExecuteResponse, OptionId } from "@/lib/types";

type DecisionState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; data: BillDecision };

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "Something went wrong. Please try again.";
}

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function Dashboard() {
  const [decision, setDecision] = useState<DecisionState>({ kind: "loading" });
  const [recommendation, setRecommendation] = useState<AgentRecommendation | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [execution, setExecution] = useState<ExecuteResponse | null>(null);
  const [busy, setBusy] = useState<"apply" | "reset" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // The deterministic numbers render first; the phrased recommendation follows.
  const refreshRecommendation = useCallback(async (signal?: AbortSignal) => {
    setRecommendation(null);
    setRecommendationError(null);
    try {
      const result = await analyze(signal);
      setRecommendation(result.recommendation);
      setDecision({ kind: "ready", data: result.decision });
    } catch (error) {
      if (!isAbort(error)) setRecommendationError(messageOf(error));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    getDashboard(controller.signal)
      .then((data) => {
        setDecision({ kind: "ready", data });
        return refreshRecommendation(controller.signal);
      })
      .catch((error: unknown) => {
        if (!isAbort(error)) setDecision({ kind: "error", message: messageOf(error) });
      });
    return () => controller.abort();
  }, [refreshRecommendation]);

  async function handleApply(optionId: OptionId) {
    setBusy("apply");
    setActionError(null);
    try {
      const result = await executeOption(optionId);
      setExecution(result);
      setDecision({ kind: "ready", data: result.decision_after });
      await refreshRecommendation();
    } catch (error) {
      setActionError(messageOf(error));
    } finally {
      setBusy(null);
    }
  }

  async function handleReset() {
    setBusy("reset");
    setActionError(null);
    try {
      const data = await resetDemo();
      setExecution(null);
      setDecision({ kind: "ready", data });
      await refreshRecommendation();
    } catch (error) {
      setActionError(messageOf(error));
    } finally {
      setBusy(null);
    }
  }

  if (decision.kind === "loading") {
    return (
      <p className="flex items-center gap-2 text-sm text-[var(--muted)]" aria-live="polite">
        <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
        Loading your accounts…
      </p>
    );
  }

  if (decision.kind === "error") {
    return (
      <div
        role="alert"
        className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm"
      >
        <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
        <div>
          <p className="font-medium">Could not load the dashboard</p>
          <p className="mt-1 text-[var(--muted)]">{decision.message}</p>
        </div>
      </div>
    );
  }

  const data = decision.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-[var(--muted)]">
          {data.customer_name} · as of {formatLongDay(data.as_of_date)}
        </p>
        <button
          type="button"
          onClick={handleReset}
          disabled={busy !== null}
          className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 text-sm font-medium transition-colors hover:bg-[var(--surface)] disabled:opacity-60"
        >
          <RotateCcw aria-hidden="true" className="h-4 w-4" />
          {busy === "reset" ? "Resetting…" : "Reset demo"}
        </button>
      </div>

      <Balances balances={data.balances} />

      {actionError && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {actionError}
        </p>
      )}
      {execution && <BeforeAfter result={execution} />}

      <div className="grid gap-6 lg:grid-cols-[1.15fr_1fr]">
        <div className="space-y-6">
          <section
            aria-labelledby="projection-heading"
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm sm:p-6"
          >
            <h2 id="projection-heading" className="flex items-center gap-2 text-lg font-semibold">
              <TrendingDown aria-hidden="true" className="h-4 w-4 text-[var(--accent)]" />
              Current account, next {data.projection.points.length - 1} days
            </h2>
            <div className="mt-4">
              <ProjectionChart projection={data.projection} />
            </div>
          </section>

          <section
            aria-labelledby="bills-heading"
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm sm:p-6"
          >
            <h2 id="bills-heading" className="flex items-center gap-2 text-lg font-semibold">
              <CalendarClock aria-hidden="true" className="h-4 w-4 text-[var(--accent)]" />
              Upcoming payments
            </h2>
            <div className="mt-2">
              <UpcomingBills
                payments={data.upcoming_payments}
                triggerId={data.triggering_payment?.payment_id ?? null}
              />
            </div>
          </section>
        </div>

        <RecommendationCard
          decision={data}
          recommendation={recommendation}
          recommendationError={recommendationError}
          applying={busy === "apply"}
          onApply={handleApply}
        />
      </div>
    </div>
  );
}
