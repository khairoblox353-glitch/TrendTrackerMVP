import Link from "next/link";
import { notFound } from "next/navigation";

import { ArticleRow } from "@/components/ArticleRow";
import { ErrorState } from "@/components/ErrorState";
import { getArticle } from "@/lib/api";
import { formatDate, formatRelativeTime } from "@/lib/format";

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

  if (!result.ok) {
    return <ErrorState title="Could not load this article" message={result.message} />;
  }

  const article = result.data;

  // `Other` buckets are diagnostics rather than real topics, so they are not offered as
  // navigation. The article remains readable and its category link is unaffected.
  const realTopics = article.topics.filter((topic) => !topic.is_fallback);

  return (
    <article className="space-y-8">
      <nav aria-label="Breadcrumb" className="text-sm text-slate-500">
        <Link href="/" className="hover:text-accent-soft">
          Home
        </Link>
        <span aria-hidden="true"> / </span>
        <Link href="/articles" className="hover:text-accent-soft">
          Articles
        </Link>
      </nav>

      <header className="space-y-3">
        <h1 className="text-2xl font-semibold leading-snug tracking-tight text-white sm:text-3xl">
          {article.title}
        </h1>
        <p className="text-sm text-slate-500">
          {article.source?.name ?? "Unknown source"}
          <span aria-hidden="true"> · </span>
          <time dateTime={article.published_at ?? undefined}>
            {formatDate(article.published_at)}
          </time>
          <span aria-hidden="true"> · </span>
          {formatRelativeTime(article.published_at)}
        </p>

        <div className="flex flex-wrap items-center gap-2">
          {article.category ? (
            <Link href={`/${article.category.slug}`} className="chip chip-active">
              {article.category.name}
            </Link>
          ) : null}
          {realTopics.map((topic) => (
            <Link key={topic.slug} href={`/trends/${topic.slug}`} className="chip">
              {topic.name}
            </Link>
          ))}
        </div>
      </header>

      <section className="card space-y-4">
        {article.summary ? (
          <div>
            <p className="label">AI summary</p>
            <p className="mt-1 text-slate-200">{article.summary}</p>
          </div>
        ) : null}

        {article.description ? (
          <div>
            <p className="label">Description</p>
            <p className="mt-1 whitespace-pre-line text-slate-300">{article.description}</p>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-4 border-t border-white/5 pt-4 text-sm">
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent-soft hover:underline"
          >
            Read the original article →
          </a>
          <span className="text-xs text-slate-500">
            Classification status: <span className="text-slate-400">{article.processing_status}</span>
          </span>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-white">More like this</h2>
        {realTopics.length === 0 ? (
          <p className="text-sm text-slate-500">
            This article was not linked to a specific topic, so there is nothing to compare.
          </p>
        ) : (
          <RelatedArticles slug={realTopics[0]!.slug} excludeId={article.id} />
        )}
      </section>
    </article>
  );
}

/** Related headlines for the article's first topic, excluding the current article. */
async function RelatedArticles({ slug, excludeId }: { slug: string; excludeId: number }) {
  const { getArticles } = await import("@/lib/api");
  const result = await getArticles({ topic: slug, page_size: 6 });

  if (!result.ok) return null;

  const items = result.data.items.filter((item) => item.id !== excludeId).slice(0, 5);
  if (items.length === 0) {
    return <p className="text-sm text-slate-500">No other articles in this topic yet.</p>;
  }

  return (
    <ul className="card divide-y divide-white/5">
      {items.map((item) => (
        <ArticleRow key={item.id} article={item} />
      ))}
    </ul>
  );
}
