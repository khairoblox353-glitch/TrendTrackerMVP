import type { TrendStatusValue } from "@/types/api";
import { STATUS_DESCRIPTIONS, STATUS_LABELS } from "@/lib/format";

/**
 * Status badge.
 *
 * The status is computed by the backend trend engine; this component only maps it to
 * a colour and label (spec 19.10).
 */

const STYLES: Record<TrendStatusValue, string> = {
  emerging: "border-amber-400/40 bg-amber-400/10 text-amber-200",
  growing: "border-emerald-400/40 bg-emerald-400/10 text-emerald-200",
  stable: "border-slate-400/30 bg-slate-400/10 text-slate-300",
  declining: "border-rose-400/40 bg-rose-400/10 text-rose-200",
};

export function TrendStatusBadge({
  status,
  isEmerging = false,
  showTooltip = true,
}: {
  status: TrendStatusValue;
  isEmerging?: boolean;
  showTooltip?: boolean;
}) {
  const resolved: TrendStatusValue = isEmerging ? "emerging" : status;

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STYLES[resolved]}`}
      title={showTooltip ? STATUS_DESCRIPTIONS[resolved] : undefined}
    >
      {STATUS_LABELS[resolved]}
    </span>
  );
}
