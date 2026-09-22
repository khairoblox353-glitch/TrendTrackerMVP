"use client";

import Link from "next/link";

import { LocaleToggle } from "@/components/LocaleToggle";
import { useI18n } from "@/lib/i18n";

/**
 * Site header.
 *
 * The category links are passed in from the layout, which fetches them from the API, so
 * the navigation can never drift from the backend taxonomy (spec 19.10). Only the
 * chrome strings are translated here; category names come from the API as-is.
 */
export function Header({
  categories,
}: {
  categories: { slug: string; name: string }[];
}) {
  const { t } = useI18n();

  return (
    <header className="border-b border-white/5 bg-surface/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-white">
          <span aria-hidden="true">📈</span> Trend Tracker
        </Link>

        <div className="flex flex-wrap items-center gap-4">
          <nav
            aria-label={t.nav.mainLabel}
            className="flex flex-wrap items-center gap-4 text-sm text-slate-400"
          >
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
              {t.nav.allTrends}
            </Link>
            <Link href="/articles" className="hover:text-accent-soft">
              {t.common.articles}
            </Link>
          </nav>
          <LocaleToggle />
        </div>
      </div>
    </header>
  );
}