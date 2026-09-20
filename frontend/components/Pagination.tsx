import Link from "next/link";

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
    <nav className="flex items-center justify-between gap-4 pt-4" aria-label="Pagination">
      {hasPrevious ? (
        <Link href={hrefFor(page - 1)} className="chip" rel="prev">
          &larr; Previous
        </Link>
      ) : (
        <span className="chip cursor-not-allowed opacity-40" aria-disabled="true">
          &larr; Previous
        </span>
      )}

      <span className="text-sm text-slate-400">
        Page <span className="tabular">{page}</span> of <span className="tabular">{pages}</span>
      </span>

      {hasNext ? (
        <Link href={hrefFor(page + 1)} className="chip" rel="next">
          Next &rarr;
        </Link>
      ) : (
        <span className="chip cursor-not-allowed opacity-40" aria-disabled="true">
          Next &rarr;
        </span>
      )}
    </nav>
  );
}
