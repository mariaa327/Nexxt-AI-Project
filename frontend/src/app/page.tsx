import { Dashboard } from "@/components/Dashboard";

export default function HomePage() {
  return (
    <div className="mx-auto max-w-5xl px-4 py-5 sm:px-6 sm:py-8">
      <h1 className="sr-only">Overdraft Guard dashboard</h1>
      <Dashboard />
    </div>
  );
}
