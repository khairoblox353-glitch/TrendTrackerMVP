"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n";
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
  const { t } = useI18n();
  return (
    <nav aria-label={t.common.categoriesLabel} className="flex flex-wrap gap-2">
      {includeAll ? (
        <Link href="/trends" className={`chip ${activeSlug ? "" : "chip-active"}`}>
          {t.common.all}
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
