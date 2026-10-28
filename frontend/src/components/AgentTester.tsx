"use client";

import {
  AlertCircle,
  CheckCircle2,
  Loader2,
  LogIn,
  Send,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, runAgent, type AgentRunResponse } from "@/lib/api";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import { getSupabaseConfig, SUPABASE_CONFIG_ERROR_MESSAGE } from "@/lib/supabase/config";

type Status =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "success"; data: AgentRunResponse }
  | { kind: "error"; message: string };

export function AgentTester() {
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const [signedIn, setSignedIn] = useState<boolean | null>(null);
  const [supabaseMissing] = useState(() => getSupabaseConfig() === null);
  const [validationError, setValidationError] = useState<string | null>(null);

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      return;
    }

    let active = true;

    void supabase.auth.getSession().then(({ data }) => {
      if (active) {
        setSignedIn(Boolean(data.session));
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (active) {
        setSignedIn(Boolean(session));
      }
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  const isLoading = status.kind === "loading";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = prompt.trim();
    if (!trimmed) {
      setValidationError("Enter a prompt before running the agent.");
      return;
    }
    if (trimmed.length > 4000) {
      setValidationError("Prompts are limited to 4000 characters.");
      return;
    }

    setValidationError(null);
    setStatus({ kind: "loading" });

    try {
      const data = await runAgent(trimmed);
      setStatus({ kind: "success", data });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : "Something went wrong while contacting the backend.";
      setStatus({ kind: "error", message });
      // A 401 means the session disappeared between render and submit.
      if (error instanceof ApiError && error.status === 401) {
        setSignedIn(false);
      }
    }
  }

  return (
    <section
      aria-labelledby="agent-tester-heading"
      className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm sm:p-6"
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
          <Sparkles aria-hidden="true" className="h-4 w-4" />
        </span>
        <div>
          <h2 id="agent-tester-heading" className="text-lg font-semibold">
            Test the agent
          </h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Sends a prompt to{" "}
            <code className="rounded bg-[var(--background)] px-1 py-0.5 font-mono text-xs">
              POST /api/agent/run
            </code>{" "}
            and stores the structured result for your account.
          </p>
        </div>
      </div>

      {supabaseMissing && (
        <SetupNotice
          title="Supabase is not configured"
          message={SUPABASE_CONFIG_ERROR_MESSAGE}
        />
      )}

      {!supabaseMissing && signedIn === false && (
        <div className="mt-5 flex flex-col gap-3 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <span>Sign in to run the agent. The backend requires a valid Supabase access token.</span>
          <Link
            href="/login"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 font-medium text-white transition-opacity hover:opacity-90"
          >
            <LogIn aria-hidden="true" className="h-4 w-4" />
            Go to sign in
          </Link>
        </div>
      )}

      <form onSubmit={handleSubmit} className="mt-5 space-y-3">
        <div>
          <label
            htmlFor="agent-prompt"
            className="block text-sm font-medium"
          >
            Prompt
          </label>
          <textarea
            id="agent-prompt"
            name="prompt"
            rows={4}
            maxLength={4000}
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Explain vector databases to a first-year CS student."
            aria-describedby="agent-prompt-help"
            aria-invalid={Boolean(validationError)}
            className="mt-1.5 w-full resize-y rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm placeholder:text-[var(--muted)]/70"
          />
          <div
            id="agent-prompt-help"
            className="mt-1 flex items-center justify-between text-xs text-[var(--muted)]"
          >
            <span>Be specific — the answer is persisted with your user ID.</span>
            <span aria-live="polite">{prompt.length}/4000</span>
          </div>
        </div>

        {validationError && (
          <p role="alert" className="text-sm text-red-600 dark:text-red-400">
            {validationError}
          </p>
        )}

        <button
          type="submit"
          disabled={isLoading || supabaseMissing}
          className="inline-flex items-center gap-2 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isLoading ? (
            <>
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
              Running…
            </>
          ) : (
            <>
              <Send aria-hidden="true" className="h-4 w-4" />
              Run agent
            </>
          )}
        </button>
      </form>

      <div className="mt-6" aria-live="polite">
        {status.kind === "loading" && (
          <p className="flex items-center gap-2 text-sm text-[var(--muted)]">
            <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            Waiting for the backend and the model…
          </p>
        )}

        {status.kind === "error" && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm"
          >
            <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">The agent run failed</p>
              <p className="mt-1 text-[var(--muted)]">{status.message}</p>
            </div>
          </div>
        )}

        {status.kind === "success" && (
          <div className="space-y-3">
            <p className="flex items-center gap-2 text-sm font-medium text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
              Agent run completed
            </p>

            <div className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
              <h3 className="text-sm font-semibold">Answer</h3>
              <p className="mt-1 whitespace-pre-wrap text-sm">{status.data.result.answer}</p>

              {status.data.result.key_points.length > 0 && (
                <>
                  <h3 className="mt-4 text-sm font-semibold">Key points</h3>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                    {status.data.result.key_points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </>
              )}

              {status.data.result.follow_up_questions.length > 0 && (
                <>
                  <h3 className="mt-4 text-sm font-semibold">Follow-up questions</h3>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
                    {status.data.result.follow_up_questions.map((question) => (
                      <li key={question}>{question}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>

            <details className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-4">
              <summary className="cursor-pointer text-sm font-medium">Raw JSON response</summary>
              <pre className="mt-2 overflow-x-auto text-xs">
                {JSON.stringify(status.data, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </section>
  );
}

function SetupNotice({ title, message }: { title: string; message: string }) {
  return (
    <div className="mt-5 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
      <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="font-medium">{title}</p>
        <p className="mt-1 text-[var(--muted)]">{message}</p>
      </div>
    </div>
  );
}
