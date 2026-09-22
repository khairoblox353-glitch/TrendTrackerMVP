"use client";

import { CategoryChips } from "@/components/CategoryChips";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Pagination } from "@/components/Pagination";
import { SearchBox } from "@/components/SearchBox";
import { SortSelect } from "@/components/SortSelect";
import { TrendTable } from "@/components/TrendTable";
import type { ApiResult } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { CategorySummary, Page, TrendSortField, TrendStatusValue, TrendSummary } from "@/types/api";

/**
 * Trend list view (spec 12).
 *
 * The page is a server component because the fetch needs the API host; the copy lives
 * here because the locale is only readable in the browser.
 */
export function TrendsView({
  trendsResult,
  categories,
  category,
  status,
  query,
  sort,
}: {
  trendsResult: ApiResult<Page<TrendSummary>>;
  categories: CategorySummary[];
  category?: string;
  status?: TrendStatusValue;
  query?: string;
  sort: TrendSortField;
}) {
  const { t } = useI18n();

  const SORT_OPTIONS = [
    { value: "-trend_score", label: t.trends.sortTrendScore },
    { value: "-growth_rate", label: t.trends.sortGrowthRate },
    { value: "-article_count", label: t.trends.sortArticleCount },
    { value: "name", label: t.trends.sortNameAsc },
  ];

  const STATUS_OPTIONS: { value: TrendStatusValue | ""; label: string }[] = [
    { value: "", label: t.trends.statusAny },
    { value: "emerging", label: t.status.labels.emerging },
    { value: "growing", label: t.status.labels.growing },
    { value: "stable", label: t.status.labels.stable },
    { value: "declining", label: t.status.labels.declining },
  ];

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-white">{t.trends.title}</h1>
        <p className="text-slate-400">{t.trends.subtitle}</p>
      </div>

      <CategoryChips categories={categories} activeSlug={category} includeAll />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="w-full sm:max-w-sm">
          <SearchBox basePath="/trends" placeholder={t.trends.searchPlaceholder} />
        </div>

        <div className="flex items-center gap-3">
          <form action="/trends" className="flex items-center gap-2 text-sm text-slate-400">
            {category ? <input type="hidden" name="category" value={category} /> : null}
            {query ? <input type="hidden" name="q" value={query} /> : null}
            <input type="hidden" name="sort" value={sort} />
            <label className="flex items-center gap-2">
              <span className="sr-only sm:not-sr-only">{t.common.statusLabel}</span>
              <select
                name="status"
                defaultValue={status ?? ""}
                className="rounded-lg border border-white/10 bg-surface-muted px-3 py-2 text-sm text-slate-100 focus:border-accent/60"
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option.value || "any"} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="submit"
              className="rounded-lg border border-white/10 bg-surface-muted px-3 py-2 text-sm hover:border-accent/50 hover:text-white"
            >
              {t.common.apply}
            </button>
          </form>

          <SortSelect basePath="/trends" options={SORT_OPTIONS} defaultValue="-trend_score" />
        </div>
      </div>

      {!trendsResult.ok ? (
        <ErrorState
          title={t.trends.couldNotLoad}
          message={trendsResult.message}
          hint={t.trends.couldNotLoadHint}
        />
      ) : trendsResult.data.items.length === 0 ? (
        <EmptyState title={t.trends.emptyTitle} description={t.trends.emptyBody} />
      ) : (
        <div className="card">
          <TrendTable trends={trendsResult.data.items} />
          <Pagination
            page={trendsResult.data.page}
            pages={trendsResult.data.pages}
            basePath="/trends"
            query={{ category, status, q: query, sort }}
          />
        </div>
      )}
    </div>
  );
}