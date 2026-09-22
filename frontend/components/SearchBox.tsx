"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

import { useI18n } from "@/lib/i18n";

/**
 * Title search box.
 *
 * Submitting only rewrites the URL; the server component re-renders with the new
 * `q` parameter. No search logic lives in the browser (spec 19.9).
 */
export function SearchBox({
  basePath,
  placeholder,
}: {
  basePath: string;
  placeholder?: string;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [value, setValue] = useState(searchParams.get("q") ?? "");
  const resolvedPlaceholder = placeholder ?? t.trends.searchPlaceholder;

  return (
    <form
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const params = new URLSearchParams(searchParams.toString());
        const trimmed = value.trim();
        if (trimmed) {
          params.set("q", trimmed);
        } else {
          params.delete("q");
        }
        params.delete("page");
        const suffix = params.toString();
        router.push(suffix ? `${basePath}?${suffix}` : basePath);
      }}
      role="search"
    >
      <input
        type="search"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder={resolvedPlaceholder}
        aria-label={resolvedPlaceholder}
        className="w-full rounded-lg border border-white/10 bg-surface-muted px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-accent/60"
      />
      <button
        type="submit"
        className="rounded-lg border border-white/10 bg-surface-muted px-4 py-2 text-sm text-slate-200 hover:border-accent/50 hover:text-white"
      >
        {t.common.search}
      </button>
    </form>
  );
}
