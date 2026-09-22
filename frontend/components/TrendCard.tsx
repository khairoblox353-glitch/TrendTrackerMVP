"use client";

import Link from "next/link";

import { formatCount, formatGrowthPercent } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
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
  const { locale, t } = useI18n();

  return (
    <Link
      href={`/trends/${trend.slug}`}
      className="card card-link flex flex-col gap-4"
      aria-label={t.trendCard.ariaLabel(trend.name, formatGrowthPercent(trend.growth_percent))}
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
          <p className="text-xs text-slate-500">{t.trendCard.growth}</p>
        </div>
        <div className="text-right">
          <p className="tabular text-lg text-slate-200">{formatCount(trend.current_count, locale)}</p>
          <p className="text-xs text-slate-500">{t.trendCard.articles}</p>
        </div>
      </div>

      <VolumeBar ratio={trend.volume_share} />

      <div className="flex items-center justify-between border-t border-white/5 pt-3">
        <span className="text-xs text-slate-500">{t.trendCard.score(String(Math.round(trend.trend_score * 100)))}</span>
        <span className="text-xs text-accent-soft">{t.trendCard.viewTrend}</span>
      </div>
    </Link>
  );
}
