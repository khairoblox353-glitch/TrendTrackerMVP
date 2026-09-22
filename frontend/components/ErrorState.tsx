"use client";

/**
 * Error state for a failed backend call.
 *
 * The message comes from the API error envelope where available, so the user sees the
 * real cause instead of a generic failure (spec 11, spec 15).
 */
import { useI18n } from "@/lib/i18n";

export function ErrorState({
  title,
  message,
  hint,
}: {
  title?: string;
  message?: string;
  hint?: string;
}) {
  const { t } = useI18n();

  return (
    <div className="card border-rose-400/30 bg-rose-400/5">
      <p className="font-medium text-rose-200">{title ?? t.errorPage.title}</p>
      {message ? <p className="mt-1 text-sm text-rose-100/80">{message}</p> : null}
      {hint ? <p className="mt-2 text-xs text-slate-400">{hint}</p> : null}
    </div>
  );
}
