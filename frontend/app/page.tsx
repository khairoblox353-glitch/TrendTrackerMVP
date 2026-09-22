import { HomeView } from "@/components/views/HomeView";
import { getArticles, getCategories, getTrends } from "@/lib/api";

export const metadata = {
  title: "Trending topics",
  description:
    "The fastest-growing topics across AI, Technology, Finance, Gaming and Health.",
};

/**
 * The dashboard reads current data on every request.
 *
 * Prerendering would bake in whatever the API returned at image build time — and because
 * the documented setup builds the frontend *before* the database is seeded, the homepage
 * and category pages would serve an empty snapshot until the next revalidation. Trend data
 * is time-sensitive and cheap to read, so these pages are rendered on demand.
 */
export const dynamic = "force-dynamic";

/**
 * Homepage (spec 12).
 *
 * Shows the five categories, the current trending topics and the newest articles.
 * Every value shown comes from the API; no scoring happens in this component
 * (spec 19.9, spec 19.10).
 *
 * This stays a server component so it can fetch through `@/lib/api` and render on every
 * request. The locale lives in `localStorage`, which the server cannot read, so the
 * translated copy lives in the client `HomeView`, which receives the raw results as JSON.
 */
export default async function HomePage() {
  const [categoriesResult, trendsResult, articlesResult, emergingResult] = await Promise.all([
    getCategories(),
    getTrends({ sort: "-trend_score", page_size: 9 }),
    getArticles({ page_size: 8 }),
    // Only the envelope count is used; `page_size: 1` keeps the extra request tiny.
    getTrends({ status: "emerging", page_size: 1 }),
  ]);

  return (
    <HomeView
      categoriesResult={categoriesResult}
      trendsResult={trendsResult}
      articlesResult={articlesResult}
      emergingResult={emergingResult}
    />
  );
}