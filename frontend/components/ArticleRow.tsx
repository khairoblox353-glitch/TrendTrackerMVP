"use client";

import Link from "next/link";

import { formatRelativeTime } from "@/lib/format";
import { useI18n } from "@/lib/i18n";
import type { ArticleDetail, ArticleSummary } from "@/types/api";

/** One headline row. Works for both the compact and full article shapes. */
export function ArticleRow({
  article,
  showSummary = false,
}: {
  article: ArticleSummary | ArticleDetail;
  showSummary?: boolean;
}) {
  const { locale, t } = useI18n();
  const detail = article as Partial<ArticleDetail>;

  // The per-category `Other` bucket is a diagnostic, not a topic, so it is not shown as
  // a tag. The article itself is still listed and still linked to its source.
  const topics = (detail.topics ?? []).filter((topic) => !topic.is_fallback);

  return (
    <li className="border-b border-white/5 py-3 last:border-b-0">
      <a
        href={article.url}
        target="_blank"
        rel="noopener noreferrer"
        className="group block"
      >
        <p className="font-medium leading-snug text-slate-100 group-hover:text-accent-soft">
          {article.title}
        </p>
        {showSummary && detail.summary ? (
          <p className="mt-1 text-sm text-slate-400">{detail.summary}</p>
        ) : null}
        <p className="mt-1 text-xs text-slate-500">
          {article.source?.name ?? t.common.unknownSource}
          <span aria-hidden="true"> · </span>
          {formatRelativeTime(article.published_at, t.relative, locale)}
          {topics.length > 0 ? (
            <>
              <span aria-hidden="true"> · </span>
              {topics.map((topic, index) => (
                <span key={topic.slug}>
                  {index > 0 ? ", " : ""}
                  <Link href={`/trends/${topic.slug}`} className="hover:text-accent-soft">
                    {topic.name}
                  </Link>
                </span>
              ))}
            </>
          ) : null}
        </p>
      </a>
    </li>
  );
}
