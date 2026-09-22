"use client";

import Link from "next/link";

import { formatCount, formatGrowthRate, formatScore } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { TrendSummary } from "@/types/api";
import { TrendStatusBadge } from "@/components/TrendStatusBadge";
import { VolumeBar } from "@/components/VolumeBar";

/**
 * Dense trend table used on the trend list page.
 *
 * Column order mirrors the sort fields the API exposes, so what the user sorts by is
 * what they see.
 */
export function TrendTable({ trends }: { trends: TrendSummary[] }) {
  const { locale, t } = useI18n();

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left">
            <th className="label py-3 pr-4">{t.table.trend}</th>
            <th className="label py-3 pr-4">{t.table.category}</th>
            <th className="label py-3 pr-4 text-right">{t.table.growth}</th>
            <th className="label py-3 pr-4 text-right">{t.table.articles}</th>
            <th className="label py-3 pr-4 text-right">{t.table.score}</th>
            <th className="label py-3 pr-4">{t.table.status}</th>
            <th className="label py-3">{t.table.volume}</th>
          </tr>
        </thead>
        <tbody>
          {trends.map((trend) => (
            <tr key={trend.id} className="border-b border-white/5 hover:bg-surface-muted/60">
              <td className="py-3 pr-4">
                <Link href={`/trends/${trend.slug}`} className="font-medium text-white hover:text-accent-soft">
                  {trend.name}
                </Link>
              </td>
              <td className="py-3 pr-4">
                <Link href={`/${trend.category.slug}`} className="text-slate-400 hover:text-accent-soft">
                  {trend.category.name}
                </Link>
              </td>
              <td className="tabular py-3 pr-4 text-right">{formatGrowthRate(trend.growth_rate)}</td>
              <td className="tabular py-3 pr-4 text-right">{formatCount(trend.current_count, locale)}</td>
              <td className="tabular py-3 pr-4 text-right">{formatScore(trend.trend_score)}</td>
              <td className="py-3 pr-4">
                <TrendStatusBadge status={trend.status} isEmerging={trend.is_emerging} />
              </td>
              <td className="w-32 py-3">
                <VolumeBar ratio={trend.volume_share} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
