import { AlertTriangle } from "lucide-react";

import { formatDay, formatSignedRon } from "@/lib/format";
import type { UpcomingPayment } from "@/lib/types";

export function UpcomingBills({
  payments,
  triggerId,
}: {
  payments: UpcomingPayment[];
  triggerId: string | null;
}) {
  if (payments.length === 0) {
    return <p className="text-sm text-[var(--muted)]">No payments scheduled.</p>;
  }

  return (
    <ul className="divide-y divide-[var(--border)]">
      {payments.map((payment) => {
        const isTrigger = payment.payment_id === triggerId;
        return (
          <li key={payment.payment_id} className="flex items-center gap-3 py-2.5 text-sm">
            <span className="w-14 shrink-0 text-[var(--muted)]">{formatDay(payment.due_date)}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{payment.merchant_name}</p>
              {payment.description && (
                <p className="truncate text-xs text-[var(--muted)]">{payment.description}</p>
              )}
              {isTrigger && (
                <p className="mt-1 inline-flex items-center gap-1 rounded-full border border-red-500/30 bg-red-500/10 px-2 py-0.5 text-xs font-medium">
                  <AlertTriangle aria-hidden="true" className="h-3 w-3 text-red-600 dark:text-red-400" />
                  Causes the overdraft
                </p>
              )}
            </div>
            <span
              className={`shrink-0 tabular-nums ${payment.amount > 0 ? "text-emerald-600 dark:text-emerald-400" : ""}`}
            >
              {formatSignedRon(payment.amount)}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
