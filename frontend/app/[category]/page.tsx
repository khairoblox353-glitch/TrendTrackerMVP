import Link from "next/link";
import { notFound } from "next/navigation";

import { ArticleList } from "@/components/ArticleList";
import { CategoryChips } from "@/components/CategoryChips";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { StatCard } from "@/components/StatCard";
import { TrendCard } from "@/components/TrendCard";
import { getArticles, getCategories, getCategory } from "@/lib/api";
import { formatCount } from "@/lib/format";

/**
 * Category page (spec 12): `/ai`, `/technology`, `/finance`, `/gaming`, `/health`.
 *
 * The slug is forwarded to the API, which is the only place that knows the five
 * categories, so adding a category later needs no frontend change.
 *
 * Rendered on every request. `generateStaticParams` is deliberately *not* used: it would
 * make Next.js prerender these routes (it takes precedence over `dynamic`), and a build
 * normally runs before the database is seeded, so the pages would serve an empty snapshot.
 */
export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params;
  const result = await getCategory(category);

  if (!result.ok) {
    return { title: "Category" };
  }

  return {
    title: result.data.name,
    description: result.data.description ?? `Trends in ${result.data.name}.`,
  };
}

export default async function CategoryPage({ params }: { params: Promise<{ category: string }> }) {
  const { category } = await params;

  const [detailResult, categoriesResult] = await Promise.all([
    getCategory(category),
    getCategories(),
  ]);

  if (!detailResult.ok && detailResult.status === 404) {
    notFound();
  }

  if (!detailResult.ok) {
    return (
      <ErrorState
        title={`Could not load the ${category} category`}
        message={detailResult.message}
      />
    );
  }

  const categoryDetail = detailResult.data;
  const categories = categoriesResult.ok ? categoriesResult.data : [];

  const articlesResult = await getArticles({ category, page_size: 10 });
  const articles = articlesResult.ok ? articlesResult.data.items : [];

  return (
    <div className="space-y-10">
      <section className="space-y-4">
        <nav aria-label="Breadcrumb" className="text-sm text-slate-500">
          <Link href="/" className="hover:text-accent-soft">
            Home
          </Link>
          <span aria-hidden="true"> / </span>
          <span className="text-slate-300">{categoryDetail.name}</span>
        </nav>

        <h1 className="text-3xl font-semibold tracking-tight text-white">{categoryDetail.name}</h1>
        {categoryDetail.description ? (
          <p className="max-w-2xl text-slate-400">{categoryDetail.description}</p>
        ) : null}

        <CategoryChips categories={categories} activeSlug={categoryDetail.slug} />
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Topics" value={formatCount(categoryDetail.topic_count)} />
        <StatCard label="Articles" value={formatCount(categoryDetail.article_count)} />
        <StatCard
          label="Leading trend"
          value={categoryDetail.trending_topic?.name ?? "—"}
          hint={
            categoryDetail.trending_topic
              ? `Score ${Math.round(categoryDetail.trending_topic.trend_score * 100)}`
              : undefined
          }
        />
      </section>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold text-white">Top trends</h2>

        {categoryDetail.top_trends.length === 0 ? (
          <EmptyState
            title="No scored topics yet"
            description="Trend snapshots have not been generated for this category."
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {categoryDetail.top_trends.map((trend, index) => (
              <TrendCard key={trend.id} trend={trend} rank={index + 1} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold text-white">Latest articles</h2>

        {!articlesResult.ok ? (
          <ErrorState title="Articles unavailable" message={articlesResult.message} />
        ) : (
          <div className="card">
            <ArticleList
              articles={articles}
              emptyMessage="No articles have been classified into this category yet."
            />
          </div>
        )}
      </section>
    </div>
  );
}
