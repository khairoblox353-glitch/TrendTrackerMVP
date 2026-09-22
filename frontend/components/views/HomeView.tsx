"use client";

import Link from "next/link";

import { ArticleRow } from "@/components/ArticleRow";
import { CategoryChips } from "@/components/CategoryChips";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { StatCard } from "@/components/StatCard";
import { TrendCard } from "@/components/TrendCard";
import type { ApiResult } from "@/lib/api";
import { formatCount, formatGrowthPercent } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { ArticleDetail, CategorySummary, Page, TrendSummary } from "@/types/api";

/**
 * Homepage body.
 *
 * The server page owns the fetching; this client view owns the copy, because the locale
 * lives in `localStorage` and only the browser can read it. The API results are passed in
 * as plain JSON and are re-read only for display (spec 19.9, spec 19.10).
 */
export function HomeView({
  categoriesResult,
  trendsResult,
  articlesResult,
  emergingResult,
}: {
  categoriesResult: ApiResult<CategorySummary[]>;
  trendsResult: ApiResult<Page<TrendSummary>>;
  articlesResult: ApiResult<Page<ArticleDetail>>;
  emergingResult: ApiResult<Page<TrendSummary>>;
}) {
  const { locale, t } = useI18n();

  const categories = categoriesResult.ok ? categoriesResult.data : [];
  const trends = trendsResult.ok ? trendsResult.data : null;
  const articles = articlesResult.ok ? articlesResult.data : null;
  const emerging = emergingResult.ok ? emergingResult.data : null;

  const leading = trends?.items[0];

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-white">Trend Tracker</h1>
          <p className="mt-2 max-w-2xl text-slate-400">
            {t.home.intro(leading ? leading.window_days : null)}
          </p>
        </div>

        <CategoryChips categories={categories} />

        {!trendsResult.ok && trendsResult.status === 0 ? (
          <ErrorState
            title={t.home.apiDownTitle}
            message={trendsResult.message}
            hint={t.home.apiDownHint}
          />
        ) : null}
      </section>

      {trends ? (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label={t.home.topicsTracked} value={formatCount(trends.total, locale)} />
          <StatCard label={t.common.articles} value={formatCount(articles?.total, locale)} />
          <StatCard
            label={t.home.leadingTrend}
            value={leading ? formatGrowthPercent(leading.growth_percent) : "—"}
            hint={leading?.name ?? t.common.notEnoughData}
            tone="positive"
          />
          <StatCard
            label={t.home.emergingTopics}
            value={formatCount(emerging?.total, locale)}
            hint={t.home.acrossAllTopics}
          />
        </section>
      ) : null}

      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold text-white">{t.home.trendingNow}</h2>
          <Link href="/trends" className="text-sm text-accent-soft hover:underline">
            {t.home.viewAllTrends}
          </Link>
        </div>

        {trends === null ? (
          <ErrorState
            title={t.home.trendsUnavailable}
            message={trendsResult.ok ? undefined : trendsResult.message}
          />
        ) : trends.items.length === 0 ? (
          <EmptyState
            title={t.home.noSnapshotsTitle}
            description={t.home.noSnapshotsBody}
            action={
              <code className="mt-2 rounded bg-surface-muted px-3 py-1 text-xs text-slate-300">
                python -m app.cli seed
              </code>
            }
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {trends.items.map((trend, index) => (
              <TrendCard key={trend.id} trend={trend} rank={index + 1} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold text-white">{t.common.latestArticles}</h2>
          <Link href="/articles" className="text-sm text-accent-soft hover:underline">
            {t.home.viewAllArticles}
          </Link>
        </div>

        {articles === null ? (
          <ErrorState
            title={t.home.articlesUnavailable}
            message={articlesResult.ok ? undefined : articlesResult.message}
          />
        ) : articles.items.length === 0 ? (
          <EmptyState
            title={t.home.noArticlesTitle}
            description={t.home.noArticlesBody}
          />
        ) : (
          <ul className="card divide-y divide-white/5">
            {articles.items.map((article) => (
              <ArticleRow key={article.id} article={article} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
