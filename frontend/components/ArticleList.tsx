import type { ArticleDetail } from "@/types/api";
import { ArticleRow } from "@/components/ArticleRow";

/** Article list with an explicit empty state (spec 12). */
export function ArticleList({
  articles,
  showSummary = false,
  emptyMessage = "No articles yet.",
}: {
  articles: ArticleDetail[];
  showSummary?: boolean;
  emptyMessage?: string;
}) {
  if (articles.length === 0) {
    return <p className="py-6 text-sm text-slate-500">{emptyMessage}</p>;
  }

  return (
    <ul className="divide-y divide-white/5">
      {articles.map((article) => (
        <ArticleRow key={article.id} article={article} showSummary={showSummary} />
      ))}
    </ul>
  );
}
