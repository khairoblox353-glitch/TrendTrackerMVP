/**
 * Formatting helpers.
 *
 * These convert backend numbers into display strings. They deliberately contain no
 * business rules: thresholds, statuses and scores are all decided by the backend
 * (spec 19.10). Nothing here should ever recalculate a score or re-derive a status.
 */

/**
 * Growth as a signed percentage string.
 *
 * The backend sends `growth_percent` already scaled, so this only formats.
 */
export function formatGrowthPercent(percent: number): string {
  if (!Number.isFinite(percent)) return "—";
  const rounded = Math.round(percent);
  if (rounded === 0) return "0%";
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

/** Growth as a signed decimal, used where space is tight (tables). */
export function formatGrowthRate(rate: number | null | undefined): string {
  if (rate === null || rate === undefined || !Number.isFinite(rate)) return "—";
  const rounded = Math.round(rate * 100);
  return `${rounded > 0 ? "+" : ""}${rounded}%`;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US").format(value);
}

/** Score shown as a 0-100 integer so the dashboard reads like a ranking. */
export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || !Number.isFinite(score)) return "—";
  return (score * 100).toFixed(0);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(parsed);
}

export function formatShortDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short" }).format(parsed);
}

/** "3h ago" style relative time, falling back to an absolute date when old. */
export function formatRelativeTime(value: string | null | undefined): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";

  const diffMs = Date.now() - parsed.getTime();
  const minutes = Math.round(diffMs / 60_000);

  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;

  return formatDate(value);
}

/** Human labels for backend status values. */
export const STATUS_LABELS = {
  emerging: "Emerging",
  growing: "Growing",
  stable: "Stable",
  declining: "Declining",
} as const;

/** Long description of each status, shown as a tooltip. */
export const STATUS_DESCRIPTIONS = {
  emerging: "No articles in the previous period, and new activity now.",
  growing: "Publishing at least 20% more than the previous period.",
  stable: "Within 20% of the previous period.",
  declining: "Publishing at least 20% less than the previous period.",
} as const;

/** Clamp a 0..1 ratio into a percentage width for the volume bars. */
export function toBarWidth(ratio: number | null | undefined, min = 4): number {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return min;
  const clamped = Math.min(Math.max(ratio, 0), 1);
  return Math.max(clamped * 100, min);
}
