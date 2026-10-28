/** Display helpers. Amounts arrive from the API already rounded to cents. */

const money = new Intl.NumberFormat("en-GB", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function formatRon(value: number): string {
  return `${money.format(value)} RON`;
}

export function formatSignedRon(value: number): string {
  return `${value > 0 ? "+" : ""}${formatRon(value)}`;
}

/** Parse an ISO date (`2026-11-05`) as a local calendar day, not UTC midnight. */
function parseDay(iso: string): Date {
  const [year, month, day] = iso.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function formatDay(iso: string): string {
  return parseDay(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export function formatLongDay(iso: string): string {
  return parseDay(iso).toLocaleDateString("en-GB", {
    weekday: "short",
    day: "numeric",
    month: "long",
  });
}
