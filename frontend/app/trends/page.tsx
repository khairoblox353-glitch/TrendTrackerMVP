import type { Metadata } from "next";

import { TrendsView } from "@/components/views/TrendsView";
import { getCategories, getTrends } from "@/lib/api";
import type { TrendSortField, TrendStatusValue } from "@/types/api";

export const metadata: Metadata = {
  title: "All trends",
  description: "Every tracked topic, ranked by trend score.",
};

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

  // Stays a server component for the fetching; the translated copy lives in the client view.
  return (
    <TrendsView
      trendsResult={trendsResult}
      categories={categories}
      category={category}
      status={status}
      query={query}
      sort={sort}
    />
  );
}