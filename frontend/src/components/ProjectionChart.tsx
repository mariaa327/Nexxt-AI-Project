"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import { formatDay, formatLongDay, formatRon } from "@/lib/format";
import type { Projection } from "@/lib/types";

// Width used for the server render, before the container is measured.
const DEFAULT_WIDTH = 640;
// Narrower than this, labels need room the axis would take: tighter layout.
const NARROW = 480;
// Closest two x-axis date labels may sit, in pixels.
const MIN_LABEL_GAP = 64;

const compact = new Intl.NumberFormat("en-GB", { notation: "compact", maximumFractionDigits: 1 });

/** 1, 2 or 5 times a power of ten, at least `raw`. */
function niceStep(raw: number): number {
  const power = 10 ** Math.floor(Math.log10(raw));
  return ([1, 2, 5, 10].find((m) => m * power >= raw) ?? 10) * power;
}

/**
 * Projected end-of-day current-account balance as a step line.
 *
 * The y-axis is fitted to the days before the next income so a small deficit
 * stays visible; the payday balance, usually far higher, is pinned to the top
 * edge with a direct label. Exact values are in the tooltip and the table.
 * The chart lays out in real pixels for its container, so text stays readable
 * on a phone instead of being scaled down.
 */
export function ProjectionChart({ projection }: { projection: Projection }) {
  const titleId = useId();
  const boxRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(DEFAULT_WIDTH);
  const [active, setActive] = useState<number | null>(null);

  useEffect(() => {
    const box = boxRef.current;
    if (!box) return;
    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.max(260, Math.round(entry.contentRect.width)));
    });
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  const narrow = width < NARROW;
  const height = narrow ? 220 : 240;
  const pad = { top: 24, right: narrow ? 12 : 20, bottom: 30, left: narrow ? 40 : 56 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const points = projection.points;
  const count = points.length;

  const incomeIndex = projection.next_income_date
    ? points.findIndex((p) => p.date === projection.next_income_date)
    : -1;
  const scaled = incomeIndex > 0 ? points.slice(0, incomeIndex) : points;
  const values = scaled.map((p) => p.balance);
  const dataMax = Math.max(0, ...values);
  const dataMin = Math.min(0, ...values);
  const step = niceStep(Math.max(dataMax - dataMin, 1) / 4);
  const yMax = Math.ceil((dataMax + step * 0.25) / step) * step;
  const yMin = Math.floor((dataMin - (dataMin < 0 ? step * 0.25 : 0)) / step) * step;

  const dx = innerW / Math.max(count - 1, 1);
  const x = (i: number) => pad.left + i * dx;
  const y = (v: number) =>
    pad.top + ((yMax - Math.min(Math.max(v, yMin), yMax)) / (yMax - yMin)) * innerH;

  const ticks: number[] = [];
  for (let v = yMin; v <= yMax + step / 2; v += step) ticks.push(v);

  // Balance changes at the start of the day it is booked: horizontal, then vertical.
  const line = points
    .map((p, i) => (i === 0 ? `M ${x(0)} ${y(p.balance)}` : `H ${x(i)} V ${y(p.balance)}`))
    .join(" ");
  const wash = `${line} V ${y(0)} H ${x(0)} Z`;

  const negative = points.flatMap((p, i) => (p.balance < 0 ? [i] : []));
  const bandStart = negative.length ? x(negative[0]) : 0;
  const bandEnd = negative.length ? x(Math.min(negative[negative.length - 1] + 1, count - 1)) : 0;
  const peakIndex = points.findIndex((p) => p.date === projection.peak_deficit_date);
  const last = points[count - 1];
  const lastOffScale = last.balance > yMax;

  // First and last day always; the first negative day only if it has room.
  const xLabels = [0, count - 1];
  const deficitIndex = negative[0];
  if (
    deficitIndex !== undefined &&
    xLabels.every((i) => Math.abs(x(i) - x(deficitIndex)) >= MIN_LABEL_GAP)
  ) {
    xLabels.splice(1, 0, deficitIndex);
  }

  function pick(event: PointerEvent<SVGSVGElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    const px = ((event.clientX - box.left) / box.width) * width;
    setActive(Math.min(count - 1, Math.max(0, Math.round((px - pad.left) / dx))));
  }

  function onKeyDown(event: KeyboardEvent<SVGSVGElement>) {
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      const delta = event.key === "ArrowRight" ? 1 : -1;
      setActive((current) => Math.min(count - 1, Math.max(0, (current ?? 0) + delta)));
    }
  }

  const activePoint = active === null ? null : points[active];

  return (
    <figure className="space-y-3">
      <figcaption id={titleId} className="sr-only">
        Projected current-account balance from {formatLongDay(points[0].date)} to{" "}
        {formatLongDay(last.date)}.
      </figcaption>

      <div ref={boxRef} className="relative">
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          className="block w-full touch-none select-none"
          role="group"
          aria-labelledby={titleId}
          tabIndex={0}
          onPointerMove={pick}
          onPointerLeave={() => setActive(null)}
          onFocus={() => setActive((current) => current ?? 0)}
          onBlur={() => setActive(null)}
          onKeyDown={onKeyDown}
        >
          {/* Overdraft stretch: status colour, always with a text label. */}
          {negative.length > 0 && (
            <g>
              <rect
                x={bandStart}
                y={pad.top}
                width={Math.max(bandEnd - bandStart, 2)}
                height={innerH}
                className="fill-red-600/10 dark:fill-red-400/15"
              />
              <circle
                cx={bandStart + 8}
                cy={pad.top - 10}
                r={4}
                className="fill-red-600 dark:fill-red-400"
              />
              <text
                x={bandStart + 16}
                y={pad.top - 6}
                className="fill-[var(--foreground)] text-[11px] font-medium"
              >
                Overdraft · {projection.deficit_days} {projection.deficit_days === 1 ? "day" : "days"}
              </text>
            </g>
          )}

          {ticks.map((v) => (
            <g key={v}>
              <line
                x1={pad.left}
                x2={width - pad.right}
                y1={y(v)}
                y2={y(v)}
                strokeWidth={1}
                className={v === 0 ? "stroke-[var(--muted)]" : "stroke-[var(--border)]"}
              />
              <text
                x={pad.left - 8}
                y={y(v) + 4}
                textAnchor="end"
                className="fill-[var(--muted)] text-[11px] tabular-nums"
              >
                {compact.format(v)}
              </text>
            </g>
          ))}

          {xLabels.map((i) => (
            <text
              key={i}
              x={x(i)}
              y={height - 8}
              textAnchor={i === 0 ? "start" : i === count - 1 ? "end" : "middle"}
              className="fill-[var(--muted)] text-[11px]"
            >
              {formatDay(points[i].date)}
            </text>
          ))}

          <path d={wash} className="fill-[var(--accent)]/10" />
          <path
            d={line}
            fill="none"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
            className="stroke-[var(--accent)]"
          />

          {peakIndex >= 0 && (
            <g>
              <circle
                cx={x(peakIndex)}
                cy={y(points[peakIndex].balance)}
                r={4}
                strokeWidth={2}
                className="fill-[var(--accent)] stroke-[var(--surface)]"
              />
              <text
                x={x(peakIndex) - 8}
                y={y(points[peakIndex].balance) + 16}
                textAnchor="end"
                className="fill-[var(--foreground)] text-[11px] font-medium tabular-nums"
              >
                {formatRon(points[peakIndex].balance)}
              </text>
            </g>
          )}

          {lastOffScale && (
            <text
              x={x(count - 1) - 8}
              y={pad.top + 12}
              textAnchor="end"
              className="fill-[var(--foreground)] text-[11px] font-medium tabular-nums"
            >
              ↑ {formatRon(last.balance)}
            </text>
          )}

          {activePoint && active !== null && (
            <g pointerEvents="none">
              <line
                x1={x(active)}
                x2={x(active)}
                y1={pad.top}
                y2={pad.top + innerH}
                strokeWidth={1}
                className="stroke-[var(--muted)]"
              />
              <circle
                cx={x(active)}
                cy={y(activePoint.balance)}
                r={4}
                strokeWidth={2}
                className="fill-[var(--accent)] stroke-[var(--surface)]"
              />
            </g>
          )}
        </svg>

        {activePoint && active !== null && (
          <div
            role="status"
            className="pointer-events-none absolute top-0 z-10 min-w-36 -translate-x-1/2 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-xs shadow-md"
            style={{ left: Math.min(width - 76, Math.max(76, x(active))) }}
          >
            <p className="text-sm font-semibold tabular-nums">
              {formatRon(activePoint.balance)}
            </p>
            <p className="text-[var(--muted)]">{formatLongDay(activePoint.date)}</p>
            {activePoint.events.map((event) => (
              <p key={event} className="mt-1 tabular-nums">
                {event} RON
              </p>
            ))}
          </div>
        )}
      </div>

      <details className="text-sm">
        <summary className="cursor-pointer text-[var(--muted)]">View as table</summary>
        <table className="mt-2 w-full text-left text-xs tabular-nums">
          <thead className="text-[var(--muted)]">
            <tr>
              <th className="py-1 font-medium">Date</th>
              <th className="py-1 text-right font-medium">Balance</th>
              <th className="py-1 pl-4 font-medium">Payments</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.date} className="border-t border-[var(--border)]">
                <td className="py-1">{formatDay(p.date)}</td>
                <td
                  className={`py-1 text-right ${p.balance < 0 ? "font-semibold text-red-600 dark:text-red-400" : ""}`}
                >
                  {formatRon(p.balance)}
                </td>
                <td className="py-1 pl-4 text-[var(--muted)]">{p.events.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
