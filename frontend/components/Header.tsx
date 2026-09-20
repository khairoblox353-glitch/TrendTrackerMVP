import Link from "next/link";

/**
 * Site header.
 *
 * The category links are passed in from the layout, which fetches them from the API, so
 * the navigation can never drift from the backend taxonomy (spec 19.10).
 */
export function Header({
  categories,
}: {
  categories: { slug: string; name: string }[];
}) {
  return (
    <header className="border-b border-white/5 bg-surface/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-white">
          <span aria-hidden="true">📈</span> Trend Tracker
        </Link>

        <nav aria-label="Main" className="flex flex-wrap items-center gap-4 text-sm text-slate-400">
          {categories.map((category) => (
            <Link
              key={category.slug}
              href={`/${category.slug}`}
              className="hover:text-accent-soft"
            >
              {category.name}
            </Link>
          ))}
          <Link href="/trends" className="hover:text-accent-soft">
            All trends
          </Link>
          <Link href="/articles" className="hover:text-accent-soft">
            Articles
          </Link>
        </nav>
      </div>
    </header>
  );
}
