import Link from "next/link";
import { notFound } from "next/navigation";

import { ArticleRow } from "@/components/ArticleRow";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { GrowthChart } from "@/components/GrowthChart";
import { StatCard } from "@/components/StatCard";
import { TrendStatusBadge } from "@/components/TrendStatusBadge";
import { VolumeBar } from "@/components/VolumeBar";
import { getTrend, getTrendHistory } from "@/lib/api";
import { formatCount, formatDate, formatGrowthPercent, formatScore } from "@/lib/format";

/**
 * Trend detail page (spec 12): `/trends/ai-agents`.
 *
 * Shows the score, growth, article counts, the history chart (drawn over the window the
 * API reports), the newest articles and the AI-generated summary. Every number is
 * computed by the backend.
 */
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const result = await getTrend(slug);

  if (!result.ok) {
    return { title: "Trend" };
  }

  return {
    title: result.data.name,
    description: result.data.summary ?? `${result.data.name} trend in ${result.data.category.name}.`,
  };
}

export default async function TrendDetailPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;

  const trendResult = await getTrend(slug);

  if (!trendResult.ok && trendResult.status === 404) {
    notFound();
  }

  if (!trendResult.ok) {
    return <ErrorState title={`Could not load ${slug}`} message={trendResult.message} />;
  }

  const trend = trendResult.data;
  const historyResult = await getTrendHistory(slug, 30, trend.window_days);
  const history = historyResult.ok ? historyResult.data : null;

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <nav aria-label="Breadcrumb" className="text-sm text-slate-500">
          <Link href="/" className="hover:text-accent-soft">
            Home
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
          label={`Growth (${trend.window_days}d)`}
          value={formatGrowthPercent(trend.growth_percent)}
          hint={`${formatCount(trend.previous_count)} → ${formatCount(trend.current_count)} articles`}
          tone={trend.growth_rate >= 0 ? "positive" : "negative"}
        />
        <StatCard label="Articles" value={formatCount(trend.current_count)} hint="In the current window" />
        <StatCard
          label="Trend score"
          value={formatScore(trend.trend_score)}
          hint="0–100, growth-weighted"
        />
        <StatCard
          label="Snapshot"
          value={formatDate(trend.snapshot_date)}
          hint={`${trend.window_days}-day window`}
        />
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-white">
          {history ? `Last ${history.points.length} days` : "Growth history"}
        </h2>

        {!historyResult.ok ? (
          <ErrorState title="History unavailable" message={historyResult.message} />
        ) : history === null ? (
          <EmptyState
            title="No snapshots for this topic yet"
            description="The trend engine has not scored this topic. Recalculating trends will create the first snapshot."
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
        <h2 className="text-xl font-semibold text-white">Summary</h2>
        <div className="card">
          {trend.summary ? (
            <p className="text-slate-300">{trend.summary}</p>
          ) : (
            <p className="text-sm text-slate-500">
              No summary has been generated for this topic yet. Summaries are written by the
              classification job from the most recent article titles.
            </p>
          )}
          <div className="mt-4">
            <VolumeBar
              ratio={trend.volume_share}
              label={`Relative volume: ${Math.round(trend.volume_share * 100)}% of the busiest topic this period`}
            />
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold text-white">Latest articles</h2>
          <Link
            href={`/articles?topic=${encodeURIComponent(trend.slug)}`}
            className="text-sm text-accent-soft hover:underline"
          >
            View all &rarr;
          </Link>
        </div>

        {trend.latest_articles.length === 0 ? (
          <EmptyState title="No articles linked to this topic yet" />
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
