"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";

/**
 * Title search box.
 *
 * Submitting only rewrites the URL; the server component re-renders with the new
 * `q` parameter. No search logic lives in the browser (spec 19.9).
 */
export function SearchBox({
  basePath,
  placeholder = "Search trends…",
  paramName = "q",
}: {
  basePath: string;
  placeholder?: string;
  paramName?: string;
}) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [value, setValue] = useState(searchParams.get(paramName) ?? "");

  return (
    <form
      className="flex gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const params = new URLSearchParams(searchParams.toString());
        const trimmed = value.trim();
        if (trimmed) {
          params.set(paramName, trimmed);
        } else {
          params.delete(paramName);
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
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full rounded-lg border border-white/10 bg-surface-muted px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-accent/60"
      />
      <button
        type="submit"
        className="rounded-lg border border-white/10 bg-surface-muted px-4 py-2 text-sm text-slate-200 hover:border-accent/50 hover:text-white"
      >
        Search
      </button>
    </form>
  );
}
