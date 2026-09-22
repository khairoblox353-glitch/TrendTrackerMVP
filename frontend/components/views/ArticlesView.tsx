"use client";

import Link from "next/link";

import { ArticleList } from "@/components/ArticleList";
import { CategoryChips } from "@/components/CategoryChips";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Pagination } from "@/components/Pagination";
import { SearchBox } from "@/components/SearchBox";
import { SortSelect } from "@/components/SortSelect";
import type { ApiResult } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { ArticleDetail, ArticleSortField, CategorySummary, Page } from "@/types/api";

/**
 * Article list view (spec 12). Filtering and paging happen in the API; this component
 * only renders the result and owns the translated copy.
 */
export function ArticlesView({
  articlesResult,
  categories,
  topicName,
  category,
  topic,
  query,
  sort,
}: {
  articlesResult: ApiResult<Page<ArticleDetail>>;
  categories: CategorySummary[];
  topicName?: string;
  category?: string;
  topic?: string;
  query?: string;
  sort: ArticleSortField;
}) {
  const { t } = useI18n();

  const SORT_OPTIONS = [
    { value: "-published_at", label: t.articles.sortNewest },
    { value: "published_at", label: t.articles.sortOldest },
    { value: "-created_at", label: t.articles.sortRecent },
    { value: "title", label: t.articles.sortTitleAsc },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-white">{t.common.articles}</h1>
        <p className="text-slate-400">
          {topicName ? t.articles.showingTopic(topicName) : t.articles.allArticles}
        </p>
      </div>

      <CategoryChips categories={categories} activeSlug={category} includeAll />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="w-full sm:max-w-sm">
          <SearchBox basePath="/articles" placeholder={t.articles.searchPlaceholder} />
        </div>
        <SortSelect basePath="/articles" options={SORT_OPTIONS} defaultValue="-published_at" />
      </div>

      {topic ? (
        <p className="text-sm text-slate-400">
          {t.articles.filteredByTopic} <span className="text-slate-200">{topicName}</span> ·{" "}
          <Link href="/articles" className="text-accent-soft hover:underline">
            {t.articles.clearFilter}
          </Link>
        </p>
      ) : null}

      {!articlesResult.ok ? (
        <ErrorState title={t.articles.couldNotLoad} message={articlesResult.message} />
      ) : articlesResult.data.items.length === 0 ? (
        <EmptyState title={t.articles.emptyTitle} description={t.articles.emptyBody} />
      ) : (
        <div className="card">
          <ArticleList articles={articlesResult.data.items} showSummary />
          <Pagination
            page={articlesResult.data.page}
            pages={articlesResult.data.pages}
            basePath="/articles"
            query={{ category, topic, q: query, sort }}
          />
        </div>
      )}
    </div>
  );
}