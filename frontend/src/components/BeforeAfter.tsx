import { ArrowRight, CheckCircle2 } from "lucide-react";

import { formatRon, formatSignedRon } from "@/lib/format";
import type { ExecuteResponse } from "@/lib/types";

export function BeforeAfter({ result }: { result: ExecuteResponse }) {
  return (
    <div
      role="status"
      className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm"
    >
      <p className="flex items-center gap-2 font-semibold text-emerald-700 dark:text-emerald-400">
        <CheckCircle2 aria-hidden="true" className="h-4 w-4" />
        Payment successful
      </p>
      <p className="mt-1">{result.message}</p>
      <div className="overflow-x-auto">
      <table className="mt-3 w-full min-w-[22rem] text-left tabular-nums">
        <thead className="text-xs text-[var(--muted)]">
          <tr>
            <th className="py-1 font-medium">Account</th>
            <th className="py-1 text-right font-medium">Before</th>
            <th className="w-6" aria-hidden="true" />
            <th className="py-1 text-right font-medium">After</th>
            <th className="py-1 text-right font-medium">Change</th>
          </tr>
        </thead>
        <tbody>
          {result.balances_after.map((after) => {
            const before = result.balances_before.find((b) => b.account_id === after.account_id);
            const change = before ? after.balance - before.balance : 0;
            return (
              <tr key={after.account_id} className="border-t border-emerald-500/20">
                <td className="py-1.5">{after.label}</td>
                <td className="py-1.5 text-right text-[var(--muted)]">
                  {before ? formatRon(before.balance) : "—"}
                </td>
                <td className="text-center text-[var(--muted)]">
                  <ArrowRight aria-hidden="true" className="inline h-3.5 w-3.5" />
                </td>
                <td className="py-1.5 text-right font-medium">{formatRon(after.balance)}</td>
                <td className="py-1.5 text-right text-[var(--muted)]">
                  {Math.abs(change) < 0.005 ? "—" : formatSignedRon(Math.round(change * 100) / 100)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
    </div>
  );
}
