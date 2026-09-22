import { notFound } from "next/navigation";

import { CategoryView } from "@/components/views/CategoryView";
import { getArticles, getCategories, getCategory } from "@/lib/api";

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

/**
 * Titles stay English: metadata is produced on the server, which cannot read the
 * `localStorage` locale, so the translated copy is rendered by the client `CategoryView`.
 */
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

  const categories = categoriesResult.ok ? categoriesResult.data : [];

  const articlesResult = await getArticles({ category, page_size: 10 });

  return (
    <CategoryView
      detailResult={detailResult}
      categories={categories}
      articlesResult={articlesResult}
      slug={category}
    />
  );
}