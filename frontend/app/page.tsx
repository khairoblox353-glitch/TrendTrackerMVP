import Link from "next/link";

import { ArticleRow } from "@/components/ArticleRow";
import { CategoryChips } from "@/components/CategoryChips";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { StatCard } from "@/components/StatCard";
import { TrendCard } from "@/components/TrendCard";
import { getArticles, getCategories, getTrends } from "@/lib/api";
import { formatCount, formatGrowthPercent } from "@/lib/format";

export const metadata = {
  title: "Trending topics",
  description:
    "The fastest-growing topics across AI, Technology, Finance, Gaming and Health.",
};

/**
 * The dashboard reads current data on every request.
 *
 * Prerendering would bake in whatever the API returned at image build time — and because
 * the documented setup builds the frontend *before* the database is seeded, the homepage
 * and category pages would serve an empty snapshot until the next revalidation. Trend data
 * is time-sensitive and cheap to read, so these pages are rendered on demand.
 */
export const dynamic = "force-dynamic";

/**
 * Homepage (spec 12).
 *
 * Shows the five categories, the current trending topics and the newest articles.
 * Every value shown comes from the API; no scoring happens in this component
 * (spec 19.9, spec 19.10).
 */
export default async function HomePage() {
  const [categoriesResult, trendsResult, articlesResult, emergingResult] = await Promise.all([
    getCategories(),
    getTrends({ sort: "-trend_score", page_size: 9 }),
    getArticles({ page_size: 8 }),
    // Only the envelope count is used; `page_size: 1` keeps the extra request tiny.
    getTrends({ status: "emerging", page_size: 1 }),
  ]);

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
            Articles are collected from RSS feeds, classified into topics and scored by
            the backend from article growth{leading ? ` over the last ${leading.window_days} days` : ""}.
          </p>
        </div>

        <CategoryChips categories={categories} />

        {!trendsResult.ok && trendsResult.status === 0 ? (
          <ErrorState
            title="The API is not responding"
            message={trendsResult.message}
            hint="Start the backend (uvicorn app.main:app) or docker compose up, then reload."
          />
        ) : null}
      </section>

      {trends ? (
        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Topics tracked" value={formatCount(trends.total)} />
          <StatCard label="Articles" value={formatCount(articles?.total)} />
          <StatCard
            label="Leading trend"
            value={leading ? formatGrowthPercent(leading.growth_percent) : "—"}
            hint={leading?.name ?? "Not enough data yet"}
            tone="positive"
          />
          <StatCard
            label="Emerging topics"
            value={formatCount(emerging?.total)}
            hint="Across all tracked topics"
          />
        </section>
      ) : null}

      <section className="space-y-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold text-white">Trending now</h2>
          <Link href="/trends" className="text-sm text-accent-soft hover:underline">
            View all trends &rarr;
          </Link>
        </div>

        {trends === null ? (
          <ErrorState title="Trends unavailable" message={trendsResult.ok ? undefined : trendsResult.message} />
        ) : trends.items.length === 0 ? (
          <EmptyState
            title="No trend snapshots yet"
            description="Run the trend recalculation to generate the first snapshot, then reload."
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
          <h2 className="text-xl font-semibold text-white">Latest articles</h2>
          <Link href="/articles" className="text-sm text-accent-soft hover:underline">
            View all articles &rarr;
          </Link>
        </div>

        {articles === null ? (
          <ErrorState title="Articles unavailable" message={articlesResult.ok ? undefined : articlesResult.message} />
        ) : articles.items.length === 0 ? (
          <EmptyState
            title="No articles ingested yet"
            description="Run the RSS collector to fetch articles from the configured feeds."
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
