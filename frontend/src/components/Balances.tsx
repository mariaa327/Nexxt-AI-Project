import { CreditCard, PiggyBank, Wallet } from "lucide-react";

import { formatRon } from "@/lib/format";
import type { AccountBalance, AccountType } from "@/lib/types";

const ICONS: Record<AccountType, typeof Wallet> = {
  CURRENT_ACCOUNT: Wallet,
  CREDIT_CARD: CreditCard,
  SAVINGS_ACCOUNT: PiggyBank,
};

function detail(account: AccountBalance): string {
  if (account.credit_limit !== null) {
    return `available of ${formatRon(account.credit_limit)} limit`;
  }
  if (account.accrued_interest !== null) {
    return `${formatRon(account.accrued_interest)} interest accrued`;
  }
  return "pays your bills and direct debits";
}

export function Balances({ balances }: { balances: AccountBalance[] }) {
  return (
    <ul className="grid gap-3 sm:grid-cols-3">
      {balances.map((account) => {
        const Icon = ICONS[account.account_type];
        return (
          <li
            key={account.account_id}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 shadow-sm"
          >
            <div className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)]/10 text-[var(--accent)]">
                <Icon aria-hidden="true" className="h-4 w-4" />
              </span>
              {account.label}
            </div>
            <p className="mt-3 text-2xl font-semibold tabular-nums">
              {formatRon(account.balance)}
            </p>
            <p className="mt-1 text-xs text-[var(--muted)]">{detail(account)}</p>
          </li>
        );
      })}
    </ul>
  );
}
