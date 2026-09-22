/**
 * Formatting helpers.
 *
 * These convert backend numbers into display strings. They deliberately contain no
 * business rules: thresholds, statuses and scores are all decided by the backend
 * (spec 19.10). Nothing here should ever recalculate a score or re-derive a status.
 *
 * Every formatter takes a `locale` (`"en"` | `"vi"`) and formats through `Intl` with an
 * explicit locale tag, so the date and number conventions follow the language the user
 * selected without any formatting decision moving into the browser.
 *
 * The three date formatters also pass `timeZone: "UTC"` to `Intl.DateTimeFormat`. They
 * now run inside client components that are server-rendered first and then hydrated on a
 * machine that may sit in another timezone; without a fixed timezone the same timestamp
 * can fall on a different calendar day in the two renders and React logs a hydration
 * mismatch. UTC also matches the backend, which stores and compares timestamps in UTC.
 */

import type { Dictionary, Locale } from "@/lib/i18n/dictionary";

/** `Intl` locale tags for number formatting. */
const NUMBER_LOCALES: Record<Locale, string> = { en: "en-US", vi: "vi-VN" };

/** `Intl` locale tags for date formatting. */
const DATE_LOCALES: Record<Locale, string> = { en: "en-GB", vi: "vi-VN" };

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

export function formatCount(value: number | null | undefined, locale: Locale): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat(NUMBER_LOCALES[locale]).format(value);
}

/** Score shown as a 0-100 integer so the dashboard reads like a ranking. */
export function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined || !Number.isFinite(score)) return "—";
  return (score * 100).toFixed(0);
}

export function formatDate(value: string | null | undefined, locale: Locale): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat(DATE_LOCALES[locale], {
    day: "2-digit",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

export function formatShortDate(value: string, locale: Locale): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat(DATE_LOCALES[locale], {
    day: "2-digit",
    month: "short",
    timeZone: "UTC",
  }).format(parsed);
}

/**
 * "3h ago" style relative time, falling back to an absolute date when old.
 *
 * The wording comes from the `relative` namespace of the dictionary; only the thresholds
 * live here. The "older than 7 days" branch delegates to `formatDate` so the fallback is
 * already locale-aware and timezone-stable.
 */
export function formatRelativeTime(
  value: string | null | undefined,
  relative: Dictionary["relative"],
  locale: Locale,
): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";

  const diffMs = Date.now() - parsed.getTime();
  const minutes = Math.round(diffMs / 60_000);

  if (minutes < 1) return relative.now;
  if (minutes < 60) return relative.minutesAgo(minutes);

  const hours = Math.round(minutes / 60);
  if (hours < 24) return relative.hoursAgo(hours);

  const days = Math.round(hours / 24);
  if (days < 7) return relative.daysAgo(days);

  return formatDate(value, locale);
}

/** Clamp a 0..1 ratio into a percentage width for the volume bars. */
export function toBarWidth(ratio: number | null | undefined, min = 4): number {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return min;
  const clamped = Math.min(Math.max(ratio, 0), 1);
  return Math.max(clamped * 100, min);
}