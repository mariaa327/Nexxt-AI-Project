"use client";

import {
  AlertCircle,
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  Loader2,
  RotateCcw,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { BeforeAfter } from "@/components/BeforeAfter";
import { Balances } from "@/components/Balances";
import { ProjectionChart } from "@/components/ProjectionChart";
import { RecommendationCard } from "@/components/RecommendationCard";
import { UpcomingBills } from "@/components/UpcomingBills";
import { VerificationModal } from "@/components/VerificationModal";
import { useRouter } from "next/navigation";

import { analyze, ApiError, getDashboard, resetDemo } from "@/lib/api";
import { getSession, subscribeSession } from "@/lib/auth";
import { formatDay, formatLongDay, formatRon } from "@/lib/format";
import type {
  AgentRecommendation,
  BillDecision,
  ExecuteResponse,
  OptionId,
} from "@/lib/types";

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

const CARD =
  "rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm sm:p-6";

export function Dashboard() {
  const [decision, setDecision] = useState<DecisionState>({ kind: "loading" });
  const [recommendation, setRecommendation] = useState<AgentRecommendation | null>(null);
  const [recommendationError, setRecommendationError] = useState<string | null>(null);
  const [execution, setExecution] = useState<ExecuteResponse | null>(null);
  const [verifying, setVerifying] = useState<{ optionId: OptionId; attempt: number } | null>(
    null,
  );
  const [resetting, setResetting] = useState(false);
  const router = useRouter();
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
    if (!getSession()) {
      router.replace("/login");
      return;
    }
    // Logged out elsewhere, or the session expired: back to the login page.
    const unsubscribe = subscribeSession(() => {
      if (!getSession()) router.replace("/login");
    });
    const controller = new AbortController();
    getDashboard(controller.signal)
      .then((data) => {
        setDecision({ kind: "ready", data });
        return refreshRecommendation(controller.signal);
      })
      .catch((error: unknown) => {
        if (!isAbort(error)) setDecision({ kind: "error", message: messageOf(error) });
      });
    return () => {
      unsubscribe();
      controller.abort();
    };
  }, [refreshRecommendation, router]);

  const handleVerified = useCallback(
    (result: ExecuteResponse) => {
      setVerifying(null);
      setExecution(result);
      setDecision({ kind: "ready", data: result.decision_after });
      void refreshRecommendation();
    },
    [refreshRecommendation],
  );

  const handleCloseVerification = useCallback(() => setVerifying(null), []);

  function handleApply(optionId: OptionId) {
    setActionError(null);
    setVerifying((current) => ({ optionId, attempt: (current?.attempt ?? 0) + 1 }));
  }

  async function handleReset() {
    setResetting(true);
    setActionError(null);
    try {
      const data = await resetDemo();
      setExecution(null);
      setDecision({ kind: "ready", data });
      await refreshRecommendation();
    } catch (error) {
      setActionError(messageOf(error));
    } finally {
      setResetting(false);
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
  const projection = data.projection;
  const atRisk = projection.first_deficit_date !== null;

  return (
    <div className="space-y-5 sm:space-y-6">
      <div className="flex items-center justify-between gap-3">
        <p className="truncate text-xs text-[var(--muted)] sm:text-sm">
          {data.customer_name} · {formatLongDay(data.as_of_date)}
        </p>
        <button
          type="button"
          onClick={handleReset}
          disabled={resetting || verifying !== null}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-[var(--border)] px-2.5 py-1 text-xs font-medium transition-colors hover:bg-[var(--surface)] disabled:opacity-60"
        >
          <RotateCcw aria-hidden="true" className="h-3.5 w-3.5" />
          {resetting ? "Resetting…" : "Reset my demo data"}
        </button>
      </div>
      {actionError && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400">
          {actionError}
        </p>
      )}

      <div className="grid gap-5 sm:gap-6 lg:grid-cols-[1.15fr_1fr]">
        <section aria-labelledby="projection-heading" className={CARD}>
          <h2
            id="projection-heading"
            className="flex items-start gap-2 text-lg font-semibold leading-snug"
          >
            {atRisk ? (
              <AlertTriangle
                aria-hidden="true"
                className="mt-1 h-4 w-4 shrink-0 text-red-600 dark:text-red-400"
              />
            ) : (
              <CheckCircle2
                aria-hidden="true"
                className="mt-1 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400"
              />
            )}
            {atRisk && projection.first_deficit_date
              ? `Overdraft on ${formatDay(projection.first_deficit_date)} unless you act`
              : `Covered until ${formatDay(projection.horizon_end)}`}
          </h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {atRisk
              ? `Your current account would reach ${formatRon(-projection.peak_deficit)} and stay negative for ${projection.deficit_days} days.`
              : `Lowest projected balance: ${formatRon(projection.lowest_balance)}.`}
          </p>
          <div className="mt-4">
            <ProjectionChart projection={projection} />
          </div>
        </section>

        <RecommendationCard
          decision={data}
          recommendation={recommendation}
          recommendationError={recommendationError}
          applying={verifying !== null}
          onApply={handleApply}
        />
      </div>

      {execution && <BeforeAfter result={execution} />}

      <Balances balances={data.balances} />

      <section aria-labelledby="bills-heading" className={CARD}>
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

      {verifying && (
        <VerificationModal
          key={verifying.attempt}
          optionId={verifying.optionId}
          onClose={handleCloseVerification}
          onSuccess={handleVerified}
        />
      )}
    </div>
  );
}
