import { Dashboard } from "@/components/Dashboard";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-12">
      <section className="max-w-2xl">
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Your money is there. It is just in the wrong account.
        </h1>
        <p className="mt-3 text-base text-[var(--muted)] sm:text-lg">
          The agent looks ahead at your bills, spots the day your current account would
          go negative, and compares every way to cover it, so you never pay overdraft
          interest while your savings sit untouched.
        </p>
      </section>

      <div className="mt-10">
        <Dashboard />
      </div>
    </div>
  );
}
