"use client";

import { AlertCircle, Loader2, LogIn, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError, getDemoUsers, login } from "@/lib/api";
import { getSession, saveSession } from "@/lib/auth";
import type { DemoUser } from "@/lib/types";

// Shown on purpose: these are fictional demo accounts for the jury.
const DEMO_PASSWORD = "overdraft2026";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demoUsers, setDemoUsers] = useState<DemoUser[]>([]);

  useEffect(() => {
    if (getSession()) {
      router.replace("/");
      return;
    }
    const controller = new AbortController();
    getDemoUsers(controller.signal)
      .then(setDemoUsers)
      .catch(() => undefined);
    return () => controller.abort();
  }, [router]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const result = await login(username, password);
      saveSession({ token: result.token, user: result.user });
      router.replace("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not log in. Please try again.");
      setSubmitting(false);
    }
  }

  function pick(user: DemoUser) {
    setUsername(user.username);
    setPassword(DEMO_PASSWORD);
    setError(null);
  }

  return (
    <div className="mx-auto max-w-md px-4 py-8 sm:py-12">
      <section className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-5 shadow-sm sm:p-6">
        <h1 className="text-xl font-semibold">Log in to your bank</h1>
        <p className="mt-1 text-sm text-[var(--muted)]">
          See your accounts, the bills coming up and how to avoid an overdraft.
        </p>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label htmlFor="username" className="block text-sm font-medium">
              Username
            </label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-1.5 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1.5 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm"
            />
          </div>

          {error && (
            <p role="alert" className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400">
              <AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? (
              <Loader2 aria-hidden="true" className="h-4 w-4 animate-spin" />
            ) : (
              <LogIn aria-hidden="true" className="h-4 w-4" />
            )}
            {submitting ? "Logging in…" : "Log in"}
          </button>
        </form>
      </section>

      {demoUsers.length > 0 && (
        <section aria-labelledby="demo-heading" className="mt-6">
          <h2 id="demo-heading" className="text-sm font-semibold">
            Demo accounts
          </h2>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Fictional clients, each with their own database. Password for all:{" "}
            <code className="rounded bg-[var(--surface)] px-1 py-0.5 font-mono">
              {DEMO_PASSWORD}
            </code>
            . Tap one to fill in the form.
          </p>
          <ul className="mt-3 grid gap-2">
            {demoUsers.map((user) => (
              <li key={user.username}>
                <button
                  type="button"
                  onClick={() => pick(user)}
                  className="flex w-full items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-left text-sm transition-colors hover:border-[var(--accent)]"
                >
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--accent)]/10 text-[var(--accent)]">
                    <UserRound aria-hidden="true" className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block font-medium">
                      {user.display_name}{" "}
                      <span className="font-mono text-xs text-[var(--muted)]">
                        {user.username}
                      </span>
                    </span>
                    <span className="block truncate text-xs text-[var(--muted)]">
                      {user.caption}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
