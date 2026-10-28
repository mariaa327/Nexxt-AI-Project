import { ArrowRight, Bot, Braces, Database, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { AgentTester } from "@/components/AgentTester";

const capabilities = [
  {
    icon: Bot,
    title: "Structured AI output",
    description:
      "The backend calls the model through the native SDK with a Pydantic schema, so responses are always validated.",
  },
  {
    icon: ShieldCheck,
    title: "Verified identity",
    description:
      "Every protected request carries a Supabase access token that FastAPI verifies against the project's JWKS keys.",
  },
  {
    icon: Database,
    title: "Persisted runs",
    description:
      "Each prompt and its structured result is stored in PostgreSQL and linked to the authenticated user.",
  },
];

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-12 sm:px-6 sm:py-16">
      <section className="max-w-2xl">
        <p className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--muted)]">
          <Braces aria-hidden="true" className="h-3.5 w-3.5" />
          Next.js 16 · FastAPI · Supabase
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
          Ship your AI feature, not your boilerplate.
        </h1>
        <p className="mt-3 text-base text-[var(--muted)] sm:text-lg">
          A small, production-conscious starter: authenticated API, structured model
          output, persisted runs and a ready-to-extend UI. Replace the example agent
          with your hackathon idea.
        </p>
        <div className="mt-5 flex flex-wrap items-center gap-3 text-sm">
          <Link
            href="/login"
            className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 font-medium text-white transition-opacity hover:opacity-90"
          >
            Sign in to run the agent
            <ArrowRight aria-hidden="true" className="h-4 w-4" />
          </Link>
          <span className="text-[var(--muted)]">
            You can browse this page without signing in.
          </span>
        </div>
      </section>

      <div className="mt-12 grid gap-6 lg:grid-cols-[1.15fr_1fr]">
        <AgentTester />

        <section aria-labelledby="capabilities-heading" className="space-y-4">
          <h2 id="capabilities-heading" className="text-lg font-semibold">
            What is already wired up
          </h2>
          <ul className="space-y-3">
            {capabilities.map(({ icon: Icon, title, description }) => (
              <li
                key={title}
                className="flex gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4"
              >
                <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
                  <Icon aria-hidden="true" className="h-4 w-4" />
                </span>
                <div>
                  <h3 className="text-sm font-semibold">{title}</h3>
                  <p className="mt-1 text-sm text-[var(--muted)]">{description}</p>
                </div>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
