/** Small labelled statistic used across the dashboard. */
export function StatCard({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "positive" | "negative";
}) {
  const valueTone =
    tone === "positive" ? "text-emerald-300" : tone === "negative" ? "text-rose-300" : "text-white";

  return (
    <div className="card">
      <p className="label">{label}</p>
      <p className={`tabular mt-1 text-2xl font-semibold ${valueTone}`}>{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </div>
  );
}
