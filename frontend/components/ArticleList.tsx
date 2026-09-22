"use client";

import { useI18n } from "@/lib/i18n";
import type { ArticleDetail } from "@/types/api";
import { ArticleRow } from "@/components/ArticleRow";

/** Article list with an explicit empty state (spec 12). */
export function ArticleList({
  articles,
  showSummary = false,
  emptyMessage,
}: {
  articles: ArticleDetail[];
  showSummary?: boolean;
  emptyMessage?: string;
}) {
  const { t } = useI18n();
  const message = emptyMessage ?? t.common.noArticlesYet;

  if (articles.length === 0) {
    return <p className="py-6 text-sm text-slate-500">{message}</p>;
  }

  return (
    <ul className="divide-y divide-white/5">
      {articles.map((article) => (
        <ArticleRow key={article.id} article={article} showSummary={showSummary} />
      ))}
    </ul>
  );
}
