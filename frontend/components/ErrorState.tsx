/**
 * Error state for a failed backend call.
 *
 * The message comes from the API error envelope where available, so the user sees the
 * real cause instead of a generic failure (spec 11, spec 15).
 */
export function ErrorState({
  title = "Something went wrong",
  message,
  hint,
}: {
  title?: string;
  message?: string;
  hint?: string;
}) {
  return (
    <div className="card border-rose-400/30 bg-rose-400/5">
      <p className="font-medium text-rose-200">{title}</p>
      {message ? <p className="mt-1 text-sm text-rose-100/80">{message}</p> : null}
      {hint ? <p className="mt-2 text-xs text-slate-400">{hint}</p> : null}
    </div>
  );
}
