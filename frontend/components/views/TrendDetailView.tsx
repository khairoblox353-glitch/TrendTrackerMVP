"use client";

import Link from "next/link";

import { ArticleRow } from "@/components/ArticleRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { GrowthChart } from "@/components/GrowthChart";
import { StatCard } from "@/components/StatCard";
import { TrendStatusBadge } from "@/components/TrendStatusBadge";
import { VolumeBar } from "@/components/VolumeBar";
import type { ApiResult } from "@/lib/api";
import { formatCount, formatDate, formatGrowthPercent, formatScore } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { TrendDetail, TrendHistory } from "@/types/api";

/**
 * Trend detail view (spec 12): `/trends/ai-agents`.
 *
 * Shows the score, growth, article counts, the history chart (drawn over the window the
 * API reports), the newest articles and the AI-generated summary. Every number is
 * computed by the backend; only the copy is decided here, from the browser locale.
 */
export function TrendDetailView({
  trendResult,
  historyResult,
  slug,
}: {
  trendResult: ApiResult<TrendDetail>;
  historyResult: ApiResult<TrendHistory | null> | null;
  slug: string;
}) {
  const { locale, t } = useI18n();

  if (!trendResult.ok) {
    return <ErrorState title={t.trendDetail.couldNotLoad(slug)} message={trendResult.message} />;
  }

  const trend = trendResult.data;
  const history = historyResult && historyResult.ok ? historyResult.data : null;
  // `message` only exists on the failure arm, so it is narrowed here rather than in the
  // JSX: `historyResult` can also be null when the trend fetch itself failed.
  const historyMessage =
    historyResult && !historyResult.ok ? historyResult.message : undefined;

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <nav aria-label={t.common.breadcrumbLabel} className="text-sm text-slate-500">
          <Link href="/" className="hover:text-accent-soft">
            {t.common.home}
          </Link>
          <span aria-hidden="true"> / </span>
          <Link href={`/${trend.category.slug}`} className="hover:text-accent-soft">
            {trend.category.name}
          </Link>
          <span aria-hidden="true"> / </span>
          <span className="text-slate-300">{trend.name}</span>
        </nav>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-white">
              {trend.is_emerging ? <span aria-hidden="true">🔥 </span> : null}
              {trend.name}
            </h1>
            {trend.description ? (
              <p className="mt-2 max-w-2xl text-slate-400">{trend.description}</p>
            ) : null}
          </div>
          <TrendStatusBadge status={trend.status} />
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={t.trendDetail.growth(trend.window_days)}
          value={formatGrowthPercent(trend.growth_percent)}
          hint={t.trendDetail.articlesHint(
            formatCount(trend.previous_count, locale),
            formatCount(trend.current_count, locale),
          )}
          tone={trend.growth_rate >= 0 ? "positive" : "negative"}
        />
        <StatCard
          label={t.common.articles}
          value={formatCount(trend.current_count, locale)}
          hint={t.trendDetail.inCurrentWindow}
        />
        <StatCard
          label={t.trendDetail.trendScore}
          value={formatScore(trend.trend_score)}
          hint={t.trendDetail.scoreHint}
        />
        <StatCard
          label={t.trendDetail.snapshot}
          value={formatDate(trend.snapshot_date, locale)}
          hint={t.trendDetail.windowHint(trend.window_days)}
        />
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-white">
          {history ? t.trendDetail.lastNDays(history.points.length) : t.trendDetail.growthHistory}
        </h2>

        {!historyResult || !historyResult.ok ? (
          <ErrorState title={t.trendDetail.historyUnavailable} message={historyMessage} />
        ) : history === null ? (
          <EmptyState
            title={t.trendDetail.noSnapshotsTitle}
            description={t.trendDetail.noSnapshotsBody}
          />
        ) : (
          <div className="card">
            <GrowthChart
              points={history.points}
              windowDays={history.window_days}
              metric="growth_rate"
            />
            <div className="mt-6 border-t border-white/5 pt-4">
              <GrowthChart
                points={history.points}
                windowDays={history.window_days}
                metric="current_count"
                height={160}
              />
            </div>
          </div>
        )}
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-white">{t.trendDetail.summary}</h2>
        <div className="card">
          {trend.summary ? (
            <p className="text-slate-300">{trend.summary}</p>
          ) : (
            <p className="text-sm text-slate-500">{t.trendDetail.noSummary}</p>
          )}
          <div className="mt-4">
            <VolumeBar
              ratio={trend.volume_share}
              label={t.trendDetail.relativeVolume(Math.round(trend.volume_share * 100))}
            />
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold text-white">{t.common.latestArticles}</h2>
          <Link
            href={`/articles?topic=${encodeURIComponent(trend.slug)}`}
            className="text-sm text-accent-soft hover:underline"
          >
            {t.trendDetail.viewAll}
          </Link>
        </div>

        {trend.latest_articles.length === 0 ? (
          <EmptyState title={t.trendDetail.noArticles} />
        ) : (
          <ul className="card divide-y divide-white/5">
            {trend.latest_articles.map((article) => (
              <ArticleRow key={article.id} article={article} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}