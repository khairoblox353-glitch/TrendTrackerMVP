import Link from "next/link";

import { formatCount, formatGrowthPercent } from "@/lib/format";
import type { TrendSummary } from "@/types/api";
import { TrendStatusBadge } from "@/components/TrendStatusBadge";
import { VolumeBar } from "@/components/VolumeBar";

/**
 * Trend card used on the homepage and category pages.
 *
 * Shows only backend-provided values: growth, article count, score and the normalized
 * volume bar (spec 13).
 */
export function TrendCard({ trend, rank }: { trend: TrendSummary; rank?: number }) {
  return (
    <Link
      href={`/trends/${trend.slug}`}
      className="card card-link flex flex-col gap-4"
      aria-label={`${trend.name}, ${formatGrowthPercent(trend.growth_percent)} growth`}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          {rank !== undefined ? (
            <span className="tabular mt-0.5 text-sm text-slate-500">{rank}.</span>
          ) : null}
          <div>
            <h3 className="font-semibold leading-tight text-white">{trend.name}</h3>
            <p className="mt-0.5 text-xs text-slate-500">{trend.category.name}</p>
          </div>
        </div>
        <TrendStatusBadge status={trend.status} isEmerging={trend.is_emerging} />
      </div>

      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="tabular text-2xl font-semibold text-white">
            {formatGrowthPercent(trend.growth_percent)}
          </p>
          <p className="text-xs text-slate-500">growth</p>
        </div>
        <div className="text-right">
          <p className="tabular text-lg text-slate-200">{formatCount(trend.current_count)}</p>
          <p className="text-xs text-slate-500">articles</p>
        </div>
      </div>

      <VolumeBar ratio={trend.volume_share} />

      <div className="flex items-center justify-between border-t border-white/5 pt-3">
        <span className="text-xs text-slate-500">Score {Math.round(trend.trend_score * 100)}</span>
        <span className="text-xs text-accent-soft">View trend &rarr;</span>
      </div>
    </Link>
  );
}
