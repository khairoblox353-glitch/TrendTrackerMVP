"use client";

import { useRouter, useSearchParams } from "next/navigation";

/**
 * Sort selector.
 *
 * The option values are exactly the sort fields documented in docs/API.md, so the UI
 * cannot send a field the API would reject.
 */
export function SortSelect({
  basePath,
  options,
  defaultValue,
  label = "Sort",
}: {
  basePath: string;
  options: { value: string; label: string }[];
  defaultValue: string;
  label?: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const current = searchParams.get("sort") ?? defaultValue;

  return (
    <label className="flex items-center gap-2 text-sm text-slate-400">
      <span className="sr-only sm:not-sr-only">{label}</span>
      <select
        value={current}
        onChange={(event) => {
          const params = new URLSearchParams(searchParams.toString());
          if (event.target.value === defaultValue) {
            params.delete("sort");
          } else {
            params.set("sort", event.target.value);
          }
          params.delete("page");
          const suffix = params.toString();
          router.push(suffix ? `${basePath}?${suffix}` : basePath);
        }}
        className="rounded-lg border border-white/10 bg-surface-muted px-3 py-2 text-sm text-slate-100 focus:border-accent/60"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
