"use client";

import Link from "next/link";

import { ArticleList } from "@/components/ArticleList";
import { CategoryChips } from "@/components/CategoryChips";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { StatCard } from "@/components/StatCard";
import { TrendCard } from "@/components/TrendCard";
import type { ApiResult } from "@/lib/api";
import { formatCount } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { ArticleDetail, CategoryDetail, CategorySummary, Page } from "@/types/api";

/**
 * Category page body.
 *
 * The server page resolves the slug, calls `notFound()` for an unknown category and
 * fetches the data; this client view only renders it with the active dictionary. Category
 * and topic names come from the API and are data, so they are never translated.
 */
export function CategoryView({
  detailResult,
  categories,
  articlesResult,
  slug,
}: {
  detailResult: ApiResult<CategoryDetail>;
  categories: CategorySummary[];
  articlesResult: ApiResult<Page<ArticleDetail>>;
  slug: string;
}) {
  const { locale, t } = useI18n();

  if (!detailResult.ok) {
    return <ErrorState title={t.category.couldNotLoad(slug)} message={detailResult.message} />;
  }

  const categoryDetail = detailResult.data;
  const articles = articlesResult.ok ? articlesResult.data.items : [];

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <nav aria-label={t.common.breadcrumbLabel} className="text-sm text-slate-500">
          <Link href="/" className="hover:text-accent-soft">
            {t.common.home}
          </Link>
          <span aria-hidden="true"> / </span>
          <span className="text-slate-300">{categoryDetail.name}</span>
        </nav>

        <h1 className="text-3xl font-semibold tracking-tight text-white">{categoryDetail.name}</h1>
        {categoryDetail.description ? (
          <p className="max-w-2xl text-slate-400">{categoryDetail.description}</p>
        ) : null}

        <CategoryChips categories={categories} activeSlug={categoryDetail.slug} />
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <StatCard label={t.category.topics} value={formatCount(categoryDetail.topic_count, locale)} />
        <StatCard label={t.common.articles} value={formatCount(categoryDetail.article_count, locale)} />
        <StatCard
          label={t.category.leadingTrend}
          value={categoryDetail.trending_topic?.name ?? "—"}
          hint={
            categoryDetail.trending_topic
              ? t.category.score(String(Math.round(categoryDetail.trending_topic.trend_score * 100)))
              : undefined
          }
        />
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-white">{t.category.topTrends}</h2>

        {categoryDetail.top_trends.length === 0 ? (
          <EmptyState
            title={t.category.noScoredTitle}
            description={t.category.noScoredBody}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {categoryDetail.top_trends.map((trend, index) => (
              <TrendCard key={trend.id} trend={trend} rank={index + 1} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">{t.common.latestArticles}</h2>

        {!articlesResult.ok ? (
          <ErrorState title={t.category.articlesUnavailable} message={articlesResult.message} />
        ) : (
          <div className="card">
            <ArticleList articles={articles} emptyMessage={t.category.emptyArticles} />
          </div>
        )}
      </section>
    </div>
  );
}
