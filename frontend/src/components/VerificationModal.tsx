"use client";

import { AlertCircle, CheckCircle2, Loader2, Lock, Smartphone } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ApiError, cancelChallenge, executeOption, getChallenge, initiateExecution } from "@/lib/api";
import { formatRon } from "@/lib/format";
import type { Challenge, ExecuteResponse, OptionId } from "@/lib/types";

type Phase =
  | { kind: "initiating" }
  | { kind: "pending"; challenge: Challenge }
  | { kind: "approved"; challenge: Challenge }
  | { kind: "executing"; challenge: Challenge }
  | { kind: "error"; message: string; challenge: Challenge | null };

const POLL_MS = 1000;
// Lets the "Approved" state register before the payment completes.
const APPROVED_PAUSE_MS = 700;

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : "Verification failed. Please try again.";
}

/**
 * Simulated 3-D Secure style verification: the payment waits for approval in
 * the banking app (approved automatically in the demo), then executes.
 * Mount with a `key` per attempt; it starts verifying immediately.
 */
export function VerificationModal({
  optionId,
  onClose,
  onSuccess,
}: {
  optionId: OptionId;
  onClose: () => void;
  onSuccess: (result: ExecuteResponse) => void;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const challengeIdRef = useRef<string | null>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "initiating" });

  useEffect(() => {
    const dialog = dialogRef.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);

  useEffect(() => {
    let stopped = false;
    const controller = new AbortController();

    async function run() {
      let challenge: Challenge | null = null;
      try {
        challenge = await initiateExecution(optionId);
        if (stopped) {
          void cancelChallenge(challenge.challenge_id).catch(() => undefined);
          return;
        }
        challengeIdRef.current = challenge.challenge_id;
        setPhase({ kind: "pending", challenge });

        let status = challenge.status;
        while (status === "pending") {
          await sleep(POLL_MS);
          if (stopped) return;
          status = (await getChallenge(challenge.challenge_id, controller.signal)).status;
        }
        if (stopped) return;
        if (status !== "approved") {
          setPhase({
            kind: "error",
            challenge,
            message:
              status === "expired"
                ? "The approval request expired. Start the payment again."
                : "The approval request is no longer valid.",
          });
          return;
        }

        setPhase({ kind: "approved", challenge });
        await sleep(APPROVED_PAUSE_MS);
        if (stopped) return;
        setPhase({ kind: "executing", challenge });
        const result = await executeOption(challenge.challenge_id);
        if (!stopped) onSuccess(result);
      } catch (error) {
        if (stopped || (error instanceof DOMException && error.name === "AbortError")) return;
        setPhase({ kind: "error", challenge, message: messageOf(error) });
      }
    }

    void run();
    return () => {
      stopped = true;
      controller.abort();
    };
  }, [optionId, onSuccess]);

  const busy = phase.kind === "approved" || phase.kind === "executing";

  function handleCancel() {
    if (busy) return;
    const id = challengeIdRef.current;
    if (id && phase.kind !== "error") {
      void cancelChallenge(id).catch(() => undefined);
    }
    onClose();
  }

  const challenge = phase.kind === "initiating" ? null : phase.challenge;

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="verify-heading"
      onCancel={(event) => {
        event.preventDefault();
        handleCancel();
      }}
      className="mx-auto mt-auto mb-0 w-full max-w-none rounded-t-2xl border border-[var(--border)] bg-[var(--surface)] p-0 text-[var(--foreground)] shadow-xl backdrop:bg-black/50 sm:my-auto sm:max-w-md sm:rounded-2xl"
    >
      <div className="p-5 sm:p-6">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
            <Lock aria-hidden="true" className="h-4 w-4" />
          </span>
          <div>
            <h2 id="verify-heading" className="text-lg font-semibold">
              Confirm payment
            </h2>
            <p className="text-xs text-[var(--muted)]">Secure verification · simulated</p>
          </div>
        </div>

        <div className="mt-5 rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
          {challenge ? (
            <>
              <p className="text-sm text-[var(--muted)]">{challenge.merchant_name}</p>
              <p className="mt-1 text-2xl font-semibold tabular-nums">
                {formatRon(challenge.amount)}
              </p>
              <p className="mt-1 text-sm text-[var(--muted)]">
                From {challenge.source_label}
                {challenge.masked_account ? ` ${challenge.masked_account}` : ""}
              </p>
            </>
          ) : (
            <p className="text-sm text-[var(--muted)]">Preparing the payment…</p>
          )}
        </div>

        <div className="mt-5 min-h-24" aria-live="polite">
          {phase.kind === "initiating" && (
            <p className="flex items-center gap-2 text-sm">
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              Sending the request to your banking app…
            </p>
          )}

          {phase.kind === "pending" && (
            <div className="flex items-start gap-3">
              <span className="relative mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[var(--accent)]/10 text-[var(--accent)]">
                <span className="absolute inset-0 animate-ping rounded-full bg-[var(--accent)]/20 motion-reduce:hidden" />
                <Smartphone aria-hidden="true" className="h-4 w-4" />
              </span>
              <div className="text-sm">
                <p className="font-medium">Waiting for approval in your banking app…</p>
                <p className="mt-1 text-[var(--muted)]">
                  Open the app on your phone and confirm the payment. In this demo it is
                  approved automatically in {phase.challenge.approve_after_seconds} s.
                </p>
              </div>
            </div>
          )}

          {phase.kind === "approved" && (
            <p className="flex items-center gap-2 text-sm font-medium text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 aria-hidden="true" className="h-5 w-5" />
              Approved in your banking app
            </p>
          )}

          {phase.kind === "executing" && (
            <p className="flex items-center gap-2 text-sm">
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              Completing the payment…
            </p>
          )}

          {phase.kind === "error" && (
            <p role="alert" className="flex items-start gap-2 text-sm">
              <AlertCircle
                aria-hidden="true"
                className="mt-0.5 h-4 w-4 shrink-0 text-red-600 dark:text-red-400"
              />
              {phase.message}
            </p>
          )}
        </div>

        <div className="mt-2 flex justify-end">
          <button
            type="button"
            onClick={handleCancel}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-4 py-2 text-sm font-medium transition-colors hover:bg-[var(--background)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {phase.kind === "error" ? "Close" : "Cancel"}
          </button>
        </div>
      </div>
    </dialog>
  );
}
