import { ShieldCheck } from "lucide-react";
import Link from "next/link";

export function Navbar() {
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
            <ShieldCheck aria-hidden="true" className="h-4 w-4" />
          </span>
          <span>Overdraft Guard</span>
        </Link>

        <span className="text-xs text-[var(--muted)]">Demo client</span>
      </nav>
    </header>
  );
}
