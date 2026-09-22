import type { Metadata } from "next";

import { ArticlesView } from "@/components/views/ArticlesView";
import { getArticles, getCategories, getTrend } from "@/lib/api";
import type { ArticleSortField } from "@/types/api";

export const metadata: Metadata = {
  title: "Articles",
  description: "Every article ingested by the collector, newest first.",
};

/**
 * Article list page (spec 12). Filtering and paging happen in the API.
 *
 * Stays a server component for the fetching; the translated copy lives in the client view.
 */
export default async function ArticlesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolved = await searchParams;
  const readParam = (key: string): string | undefined => {
    const value = resolved[key];
    return Array.isArray(value) ? value[0] : value;
  };

  const category = readParam("category");
  const topic = readParam("topic");
  const query = readParam("q");
  const sort = (readParam("sort") as ArticleSortField | undefined) ?? "-published_at";
  const page = Number.parseInt(readParam("page") ?? "1", 10) || 1;

  const [articlesResult, categoriesResult] = await Promise.all([
    getArticles({ category, topic, q: query, sort, page, page_size: 20 }),
    getCategories(),
  ]);

  const categories = categoriesResult.ok ? categoriesResult.data : [];

  // When filtered by topic, show which trend that is, so the filter is self-evident.
  const topicResult = topic ? await getTrend(topic) : null;
  const topicName = topicResult?.ok ? topicResult.data.name : topic;

  return (
    <ArticlesView
      articlesResult={articlesResult}
      categories={categories}
      topicName={topicName}
      category={category}
      topic={topic}
      query={query}
      sort={sort}
    />
  );
}