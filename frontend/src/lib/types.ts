/** Shared API types mirrored from the FastAPI schemas (app/schemas/insights.py). */

export type OptionId = "credit_card" | "savings" | "overdraft";

export type AccountType = "CURRENT_ACCOUNT" | "CREDIT_CARD" | "SAVINGS_ACCOUNT";

export type AccountBalance = {
  account_id: string;
  account_type: AccountType;
  label: string;
  balance: number;
  credit_limit: number | null;
  accrued_interest: number | null;
};

export type CategoryTotal = {
  category: string;
  amount: number;
};

export type RecurringObligation = {
  merchant_name: string;
  account_id: string;
  category: string | null;
  amount: number;
  day_of_month: number;
  next_due_date: string;
};

export type SituationSummary = {
  period_start: string | null;
  period_end: string | null;
  total_income: number;
  total_spend: number;
  spend_by_category: CategoryTotal[];
  recurring: RecurringObligation[];
};

export type UpcomingPayment = {
  payment_id: string;
  account_id: string;
  due_date: string;
  amount: number;
  merchant_name: string;
  category: string | null;
  description: string;
};

export type ProjectionPoint = {
  date: string;
  balance: number;
  events: string[];
};

export type Projection = {
  points: ProjectionPoint[];
  horizon_end: string;
  next_income_date: string | null;
  lowest_balance: number;
  lowest_balance_date: string;
  first_deficit_date: string | null;
  peak_deficit: number;
  peak_deficit_date: string | null;
  deficit_days: number;
  deficit_exposure: number;
};

export type CostOption = {
  option_id: OptionId;
  label: string;
  action: string;
  amount: number;
  cost: number;
  formula: string;
  explanation: string;
  assumptions: string[];
  prevents_overdraft: boolean;
  feasible: boolean;
  source_account_id: string | null;
};

export type BillDecision = {
  customer_name: string;
  as_of_date: string;
  payments_source: "scheduled" | "recurring_history";
  balances: AccountBalance[];
  situation: SituationSummary;
  upcoming_payments: UpcomingPayment[];
  projection: Projection;
  no_action_needed: boolean;
  triggering_payment: UpcomingPayment | null;
  options: CostOption[];
  recommended_option_id: OptionId | null;
  saving_vs_doing_nothing: number;
};

export type AgentRecommendation = {
  status: "action_required" | "no_risk";
  recommended_option_id: OptionId | null;
  headline: string;
  reasons: string[];
  trade_offs: string[];
  generated_by: "llm" | "rules";
  fallback_reason: string | null;
};

export type AnalyzeResponse = {
  decision: BillDecision;
  recommendation: AgentRecommendation;
  task_id: string | null;
  persisted: boolean;
};

export type ExecuteResponse = {
  option_id: OptionId;
  message: string;
  balances_before: AccountBalance[];
  balances_after: AccountBalance[];
  decision_after: BillDecision;
};

export type ChallengeStatus = "pending" | "approved" | "expired" | "cancelled" | "used";

/** Simulated payment verification awaiting approval in the banking app. */
export type Challenge = {
  challenge_id: string;
  option_id: OptionId;
  merchant_name: string;
  amount: number;
  source_label: string;
  masked_account: string | null;
  status: ChallengeStatus;
  approve_after_seconds: number;
  expires_in_seconds: number;
};

export type UserInfo = {
  username: string;
  display_name: string;
};

export type DemoUser = UserInfo & { caption: string };

export type LoginResponse = {
  token: string;
  user: UserInfo;
};
