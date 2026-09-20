/**
 * Dependency-free trend chart.
 *
 * Renders an inline SVG line chart of the `growth_rate` series (with the article count
 * as the y-axis label context). A charting library would be the single largest
 * frontend dependency for one line, so the SVG is generated directly (ADR-007).
 *
 * This is a server component: no state, no effects, no event handlers.
 */

import { formatShortDate } from "@/lib/format";
import type { SnapshotPoint } from "@/types/api";

const WIDTH = 720;
const HEIGHT = 200;
const PADDING = { top: 16, right: 16, bottom: 28, left: 44 };

export function GrowthChart({
  points,
  metric = "growth_rate",
  height = HEIGHT,
}: {
  points: SnapshotPoint[];
  metric?: "growth_rate" | "current_count";
  height?: number;
}) {
  if (points.length === 0) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-white/10 text-sm text-slate-500">
        No history available yet.
      </div>
    );
  }

  const values = points.map((point) => (metric === "growth_rate" ? point.growth_rate : point.current_count));

  const rawMin = Math.min(...values, 0);
  const rawMax = Math.max(...values, 1);
  const span = rawMax - rawMin || 1;
  const min = rawMin - span * 0.1;
  const max = rawMax + span * 0.1;

  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = height - PADDING.top - PADDING.bottom;
  const step = points.length > 1 ? plotWidth / (points.length - 1) : 0;

  const x = (index: number) => PADDING.left + index * step;
  const y = (value: number) => PADDING.top + plotHeight - ((value - min) / (max - min)) * plotHeight;

  const linePath = points
    .map((point, index) => {
      const value = metric === "growth_rate" ? point.growth_rate : point.current_count;
      return `${index === 0 ? "M" : "L"} ${x(index).toFixed(2)} ${y(value).toFixed(2)}`;
    })
    .join(" ");

  const areaPath = `${linePath} L ${x(points.length - 1).toFixed(2)} ${(PADDING.top + plotHeight).toFixed(2)} L ${x(0).toFixed(2)} ${(PADDING.top + plotHeight).toFixed(2)} Z`;

  // Four horizontal gridlines with the zero line emphasised when growth is shown.
  const gridValues = [max, max - (max - min) / 3, min + (max - min) / 3, min];
  const zeroY = min <= 0 && max >= 0 ? y(0) : null;

  const labelEvery = Math.max(1, Math.ceil(points.length / 7));

  return (
    <figure className="w-full">
      <svg
        viewBox={`0 0 ${WIDTH} ${height}`}
        className="h-auto w-full"
        role="img"
        aria-label={
          metric === "growth_rate"
            ? `Growth rate over ${points.length} days`
            : `Article count over ${points.length} days`
        }
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="trend-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4f7cff" stopOpacity="0.35" />
            <stop offset="100%" stopColor="#4f7cff" stopOpacity="0" />
          </linearGradient>
        </defs>

        {gridValues.map((value, index) => (
          <g key={index}>
            <line
              x1={PADDING.left}
              x2={WIDTH - PADDING.right}
              y1={y(value)}
              y2={y(value)}
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="1"
            />
            <text
              x={PADDING.left - 8}
              y={y(value) + 4}
              textAnchor="end"
              className="fill-slate-500"
              fontSize="11"
            >
              {metric === "growth_rate" ? `${Math.round(value * 100)}%` : Math.round(value)}
            </text>
          </g>
        ))}

        {zeroY !== null ? (
          <line
            x1={PADDING.left}
            x2={WIDTH - PADDING.right}
            y1={zeroY}
            y2={zeroY}
            stroke="rgba(255,255,255,0.25)"
            strokeWidth="1"
            strokeDasharray="4 4"
          />
        ) : null}

        <path d={areaPath} fill="url(#trend-area)" />
        <path d={linePath} fill="none" stroke="#7fa0ff" strokeWidth="2" strokeLinejoin="round" />

        {points.map((point, index) =>
          index % labelEvery === 0 || index === points.length - 1 ? (
            <text
              key={point.date}
              x={x(index)}
              y={height - 8}
              textAnchor="middle"
              className="fill-slate-500"
              fontSize="11"
            >
              {formatShortDate(point.date)}
            </text>
          ) : null,
        )}
      </svg>
      <figcaption className="mt-2 text-xs text-slate-500">
        {metric === "growth_rate"
          ? "Growth rate per day (current 7-day window vs the previous 7 days)."
          : "Articles per 7-day window."}
      </figcaption>
    </figure>
  );
}
