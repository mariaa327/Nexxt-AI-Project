"use client";

import { LogIn, LogOut, Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import { getSupabaseConfig } from "@/lib/supabase/config";

export function Navbar() {
  const [email, setEmail] = useState<string | null>(null);
  // Reading public env vars is safe during render, so configuration is known
  // immediately instead of being set from an effect.
  const [configured] = useState(() => getSupabaseConfig() !== null);
  const [signingOut, setSigningOut] = useState(false);

  useEffect(() => {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      return;
    }

    // Guards against state updates from a subscription that has already been
    // torn down (e.g. React 19 Strict Mode double-invoked effects).
    let active = true;

    void supabase.auth.getSession().then(({ data }) => {
      if (active) {
        setEmail(data.session?.user.email ?? null);
      }
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (active) {
        setEmail(session?.user.email ?? null);
      }
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  async function handleSignOut() {
    const supabase = getSupabaseBrowserClient();
    if (!supabase) {
      return;
    }

    setSigningOut(true);
    try {
      await supabase.auth.signOut();
      setEmail(null);
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <header className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--background)]/85 backdrop-blur">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-6"
      >
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold tracking-tight"
        >
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
            <Sparkles aria-hidden="true" className="h-4 w-4" />
          </span>
          <span>Hackathon Starter</span>
        </Link>

        <div className="flex items-center gap-3 text-sm">
          <Link
            href="/"
            className="hidden rounded-md px-2 py-1 text-[var(--muted)] transition-colors hover:text-[var(--foreground)] sm:block"
          >
            Dashboard
          </Link>

          {!configured ? (
            <span className="hidden text-xs text-[var(--muted)] sm:inline">
              Supabase not configured
            </span>
          ) : email ? (
            <>
              <span
                className="hidden max-w-48 truncate text-[var(--muted)] sm:inline"
                title={email}
              >
                {email}
              </span>
              <button
                type="button"
                onClick={handleSignOut}
                disabled={signingOut}
                className="inline-flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 font-medium transition-colors hover:bg-[var(--surface)] disabled:opacity-60"
              >
                <LogOut aria-hidden="true" className="h-4 w-4" />
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            </>
          ) : (
            <Link
              href="/login"
              className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-3 py-1.5 font-medium text-white transition-opacity hover:opacity-90"
            >
              <LogIn aria-hidden="true" className="h-4 w-4" />
              Sign in
            </Link>
          )}
        </div>
      </nav>
    </header>
  );
}
