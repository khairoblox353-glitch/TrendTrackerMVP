import Link from "next/link";

import type { CategorySummary } from "@/types/api";

/** Category filter chips. Active state is driven by the current route (spec 12). */
export function CategoryChips({
  categories,
  activeSlug,
  includeAll = false,
}: {
  categories: CategorySummary[];
  activeSlug?: string;
  includeAll?: boolean;
}) {
  return (
    <nav aria-label="Categories" className="flex flex-wrap gap-2">
      {includeAll ? (
        <Link href="/trends" className={`chip ${activeSlug ? "" : "chip-active"}`}>
          All
        </Link>
      ) : null}
      {categories.map((category) => (
        <Link
          key={category.slug}
          href={`/${category.slug}`}
          className={`chip ${activeSlug === category.slug ? "chip-active" : ""}`}
          aria-current={activeSlug === category.slug ? "page" : undefined}
        >
          {category.name}
        </Link>
      ))}
    </nav>
  );
}
