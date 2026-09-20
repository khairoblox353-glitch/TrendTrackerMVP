import Link from "next/link";
import type { Metadata } from "next";

import { ArticleList } from "@/components/ArticleList";
import { CategoryChips } from "@/components/CategoryChips";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { Pagination } from "@/components/Pagination";
import { SearchBox } from "@/components/SearchBox";
import { SortSelect } from "@/components/SortSelect";
import { getArticles, getCategories, getTrend } from "@/lib/api";
import type { ArticleSortField } from "@/types/api";

export const metadata: Metadata = {
  title: "Articles",
  description: "Every article ingested by the collector, newest first.",
};

const SORT_OPTIONS = [
  { value: "-published_at", label: "Newest first" },
  { value: "published_at", label: "Oldest first" },
  { value: "-created_at", label: "Recently ingested" },
  { value: "title", label: "Title (A–Z)" },
];

/** Article list page (spec 12). Filtering and paging happen in the API. */
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
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-white">Articles</h1>
        <p className="text-slate-400">
          {topicName
            ? `Showing articles classified into “${topicName}”.`
            : "Every article stored from the configured RSS feeds."}
        </p>
      </div>

      <CategoryChips categories={categories} activeSlug={category} includeAll />

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="w-full sm:max-w-sm">
          <SearchBox basePath="/articles" placeholder="Search headlines…" />
        </div>
        <SortSelect basePath="/articles" options={SORT_OPTIONS} defaultValue="-published_at" />
      </div>

      {topic ? (
        <p className="text-sm text-slate-400">
          Filtered by topic <span className="text-slate-200">{topicName}</span> ·{" "}
          <Link href="/articles" className="text-accent-soft hover:underline">
            clear filter
          </Link>
        </p>
      ) : null}

      {!articlesResult.ok ? (
        <ErrorState title="Could not load articles" message={articlesResult.message} />
      ) : articlesResult.data.items.length === 0 ? (
        <EmptyState
          title="No articles found"
          description="Run the collector to ingest feeds, or adjust the filters."
        />
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
