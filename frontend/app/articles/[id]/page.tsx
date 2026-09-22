import { notFound } from "next/navigation";

import { ArticleDetailView } from "@/components/views/ArticleDetailView";
import { getArticle } from "@/lib/api";
import type { ArticleSummary } from "@/types/api";

/** Single article page (spec 12). */
export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const result = await getArticle(id);

  if (!result.ok) {
    return { title: "Article" };
  }

  return { title: result.data.title };
}

export default async function ArticlePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  const result = await getArticle(id);

  if (!result.ok && result.status === 404) {
    notFound();
  }

  // `Other` buckets are diagnostics rather than real topics, so they are not offered as
  // navigation. The article remains readable and its category link is unaffected.
  const realTopics = result.ok
    ? result.data.topics.filter((topic) => !topic.is_fallback)
    : [];

  const relatedArticles =
    result.ok && realTopics.length > 0
      ? await getRelatedArticles(realTopics[0]!.slug, result.data.id)
      : null;

  return <ArticleDetailView articleResult={result} relatedArticles={relatedArticles} />;
}

/** Related headlines for the article's first topic, excluding the current one. Returns
 *  null when the lookup fails, so the view can tell "failed" apart from "none found". */
async function getRelatedArticles(slug: string, excludeId: number): Promise<ArticleSummary[] | null> {
  const { getArticles } = await import("@/lib/api");
  const result = await getArticles({ topic: slug, page_size: 6 });
  if (!result.ok) return null;
  return result.data.items.filter((item) => item.id !== excludeId).slice(0, 5);
}
