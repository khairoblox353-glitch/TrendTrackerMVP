import { notFound } from "next/navigation";

import { TrendDetailView } from "@/components/views/TrendDetailView";
import { getTrend, getTrendHistory } from "@/lib/api";

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

  // The server cannot know the stored locale, so the fallback stays English.
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

  // Fetched here so the 404 above still wins; the copy is rendered by the client view.
  const historyResult = trendResult.ok
    ? await getTrendHistory(slug, 30, trendResult.data.window_days)
    : null;

  return <TrendDetailView trendResult={trendResult} historyResult={historyResult} slug={slug} />;
}