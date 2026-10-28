"use client";

import { LogOut, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";

import { clearSession, getSession, subscribeSession } from "@/lib/auth";

export function Navbar() {
  const router = useRouter();
  const session = useSyncExternalStore(subscribeSession, getSession, () => null);

  function handleLogout() {
    clearSession();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-10 border-b border-[var(--border)] bg-[var(--background)]/85 backdrop-blur">
      <nav
        aria-label="Main navigation"
        className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-6"
      >
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] text-white">
            <ShieldCheck aria-hidden="true" className="h-4 w-4" />
          </span>
          <span>Overdraft Guard</span>
        </Link>

        {session && (
          <div className="flex min-w-0 items-center gap-3 text-sm">
            <span className="truncate text-[var(--muted)]">{session.user.display_name}</span>
            <button
              type="button"
              onClick={handleLogout}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 font-medium transition-colors hover:bg-[var(--surface)]"
            >
              <LogOut aria-hidden="true" className="h-4 w-4" />
              Log out
            </button>
          </div>
        )}
      </nav>
    </header>
  );
}
