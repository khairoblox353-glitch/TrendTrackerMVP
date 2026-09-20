import type { Metadata } from "next";

import { CategoryChips } from "@/components/CategoryChips";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Pagination } from "@/components/Pagination";
import { SearchBox } from "@/components/SearchBox";
import { SortSelect } from "@/components/SortSelect";
import { TrendTable } from "@/components/TrendTable";
import { getCategories, getTrends } from "@/lib/api";
import type { TrendSortField, TrendStatusValue } from "@/types/api";

export const metadata: Metadata = {
  title: "All trends",
  description: "Every tracked topic, ranked by trend score.",
};

const SORT_OPTIONS = [
  { value: "-trend_score", label: "Trend score" },
  { value: "-growth_rate", label: "Growth rate" },
  { value: "-article_count", label: "Article count" },
  { value: "name", label: "Name (A–Z)" },
];

const STATUS_OPTIONS: { value: TrendStatusValue | ""; label: string }[] = [
  { value: "", label: "Any status" },
  { value: "emerging", label: "Emerging" },
  { value: "growing", label: "Growing" },
  { value: "stable", label: "Stable" },
  { value: "declining", label: "Declining" },
];

/**
 * Trend list page (spec 12).
 *
 * Filters, sorting and paging are all server-side: this component only translates URL
 * search parameters into an API query (spec 19.9).
 */
export default async function TrendsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolved = await searchParams;
  const readParam = (key: string): string | undefined => {
    const value = resolved[key];
    if (Array.isArray(value)) return value[0];
    return value;
  };

  const category = readParam("category");
  const status = readParam("status") as TrendStatusValue | undefined;
  const query = readParam("q");
  const sort = (readParam("sort") as TrendSortField | undefined) ?? "-trend_score";
  const page = Number.parseInt(readParam("page") ?? "1", 10) || 1;

  const [trendsResult, categoriesResult] = await Promise.all([
    getTrends({
      category,
      status: status || undefined,
      q: query,
      sort,
      page,
      page_size: 20,
    }),
    getCategories(),
  ]);

  const categories = categoriesResult.ok ? categoriesResult.data : [];

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-white">All trends</h1>
        <p className="text-slate-400">
          The latest snapshot for every tracked topic, ranked by the backend trend score.
        </p>
      </div>

      <CategoryChips categories={categories} activeSlug={category} includeAll />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="w-full sm:max-w-sm">
          <SearchBox basePath="/trends" placeholder="Search topics…" />
        </div>

        <div className="flex items-center gap-3">
          <form action="/trends" className="flex items-center gap-2 text-sm text-slate-400">
            {category ? <input type="hidden" name="category" value={category} /> : null}
            {query ? <input type="hidden" name="q" value={query} /> : null}
            <input type="hidden" name="sort" value={sort} />
            <label className="flex items-center gap-2">
              <span className="sr-only sm:not-sr-only">Status</span>
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
              Apply
            </button>
          </form>

          <SortSelect basePath="/trends" options={SORT_OPTIONS} defaultValue="-trend_score" />
        </div>
      </div>

      {!trendsResult.ok ? (
        <ErrorState
          title="Could not load trends"
          message={trendsResult.message}
          hint="Check that the FastAPI backend is running."
        />
      ) : trendsResult.data.items.length === 0 ? (
        <EmptyState
          title="No trends match these filters"
          description="Try a different category, status or search term."
        />
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
