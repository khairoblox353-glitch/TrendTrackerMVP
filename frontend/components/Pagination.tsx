"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n";

/**
 * Pagination control.
 *
 * `basePath` plus the other query values are passed through untouched, so paging never
 * silently drops an active filter.
 */
export function Pagination({
  page,
  pages,
  basePath,
  query = {},
}: {
  page: number;
  pages: number;
  basePath: string;
  query?: Record<string, string | undefined>;
}) {
  const { t } = useI18n();

  if (pages <= 1) return null;

  const hrefFor = (target: number) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value) params.set(key, value);
    }
    if (target > 1) params.set("page", String(target));
    const suffix = params.toString();
    return suffix ? `${basePath}?${suffix}` : basePath;
  };

  const hasPrevious = page > 1;
  const hasNext = page < pages;

  return (
    <nav className="flex items-center justify-between gap-4 pt-4" aria-label={t.common.paginationLabel}>
      {hasPrevious ? (
        <Link href={hrefFor(page - 1)} className="chip" rel="prev">
          {t.common.previous}
        </Link>
      ) : (
        <span className="chip cursor-not-allowed opacity-40" aria-disabled="true">
          {t.common.previous}
        </span>
      )}

      <span className="text-sm text-slate-400">
        {t.common.pageOf(page, pages)}
      </span>

      {hasNext ? (
        <Link href={hrefFor(page + 1)} className="chip" rel="next">
          {t.common.next}
        </Link>
      ) : (
        <span className="chip cursor-not-allowed opacity-40" aria-disabled="true">
          {t.common.next}
        </span>
      )}
    </nav>
  );
}
