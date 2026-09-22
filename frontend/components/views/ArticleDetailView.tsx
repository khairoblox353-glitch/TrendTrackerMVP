"use client";

import Link from "next/link";

import { ArticleRow } from "@/components/ArticleRow";
import { ErrorState } from "@/components/ErrorState";
import type { ApiResult } from "@/lib/api";
import { formatDate, formatRelativeTime } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { ArticleDetail, ArticleSummary } from "@/types/api";

/** Single article view (spec 12). */
export function ArticleDetailView({
  articleResult,
  relatedArticles,
}: {
  articleResult: ApiResult<ArticleDetail>;
  relatedArticles: ArticleSummary[] | null;
}) {
  const { locale, t } = useI18n();

  if (!articleResult.ok) {
    return <ErrorState title={t.articleDetail.couldNotLoad} message={articleResult.message} />;
  }

  const article = articleResult.data;

  // `Other` buckets are diagnostics rather than real topics, so they are not offered as
  // navigation. The article remains readable and its category link is unaffected.
  const realTopics = article.topics.filter((topic) => !topic.is_fallback);

  return (
    <article className="space-y-8">
      <nav aria-label={t.common.breadcrumbLabel} className="text-sm text-slate-500">
        <Link href="/" className="hover:text-accent-soft">
          {t.common.home}
        </Link>
        <span aria-hidden="true"> / </span>
        <Link href="/articles" className="hover:text-accent-soft">
          {t.common.articles}
        </Link>
      </nav>

      <header className="space-y-3">
        <h1 className="text-2xl font-semibold leading-snug tracking-tight text-white sm:text-3xl">
          {article.title}
        </h1>
        <p className="text-sm text-slate-500">
          {article.source?.name ?? t.common.unknownSource}
          <span aria-hidden="true"> · </span>
          <time dateTime={article.published_at ?? undefined}>
            {formatDate(article.published_at, locale)}
          </time>
          <span aria-hidden="true"> · </span>
          {formatRelativeTime(article.published_at, t.relative, locale)}
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
            <p className="label">{t.articleDetail.aiSummary}</p>
            <p className="mt-1 text-slate-200">{article.summary}</p>
          </div>
        ) : null}

        {article.description ? (
          <div>
            <p className="label">{t.articleDetail.description}</p>
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
            {t.articleDetail.readOriginal}
          </a>
          <span className="text-xs text-slate-500">
            {t.articleDetail.classificationStatus}{" "}
            <span className="text-slate-400">{article.processing_status}</span>
          </span>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-white">{t.articleDetail.moreLikeThis}</h2>
        {realTopics.length === 0 ? (
          <p className="text-sm text-slate-500">{t.articleDetail.noTopic}</p>
        ) : relatedArticles === null ? null : relatedArticles.length === 0 ? (
          <p className="text-sm text-slate-500">{t.articleDetail.noOtherArticles}</p>
        ) : (
          <ul className="card divide-y divide-white/5">
            {relatedArticles.map((item) => (
              <ArticleRow key={item.id} article={item} />
            ))}
          </ul>
        )}
      </section>
    </article>
  );
}
