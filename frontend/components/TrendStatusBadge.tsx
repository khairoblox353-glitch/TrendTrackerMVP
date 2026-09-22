"use client";

import type { TrendStatusValue } from "@/types/api";
import { useI18n } from "@/lib/i18n";

/**
 * Status badge.
 *
 * The status is computed by the backend trend engine; this component only maps it to
 * a colour and label (spec 19.10). It deliberately does not re-derive the status from
 * `is_emerging`: the engine already returns `emerging` for those topics, and deriving it
 * again here could disagree with the list view.
 */

const STYLES: Record<TrendStatusValue, string> = {
  emerging: "border-amber-400/40 bg-amber-400/10 text-amber-200",
  growing: "border-emerald-400/40 bg-emerald-400/10 text-emerald-200",
  stable: "border-slate-400/30 bg-slate-400/10 text-slate-300",
  declining: "border-rose-400/40 bg-rose-400/10 text-rose-200",
};

export function TrendStatusBadge({
  status,
}: {
  status: TrendStatusValue;
  /**
   * Accepted so existing callers keep compiling, but deliberately ignored: the engine
   * already returns `emerging` when `is_emerging` is set, so re-deriving the status here
   * could make the badge disagree with the API (and with the trend list).
   */
  isEmerging?: boolean;
}) {
  const { t } = useI18n();

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}
      title={t.status.descriptions[status]}
    >
      {t.status.labels[status]}
    </span>
  );
}