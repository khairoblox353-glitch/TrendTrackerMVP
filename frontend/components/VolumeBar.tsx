import { toBarWidth } from "@/lib/format";

/**
 * Volume bar.
 *
 * `volume_share` is the backend's normalized article volume (0..1) for the current
 * period, so the bar never recomputes anything itself.
 */
export function VolumeBar({
  ratio,
  label,
  className = "",
}: {
  ratio: number;
  label?: string;
  className?: string;
}) {
  const width = toBarWidth(ratio);

  return (
    <div className={className}>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent to-accent-soft"
          style={{ width: `${width}%` }}
          role="presentation"
        />
      </div>
      {label ? <p className="mt-1 text-xs text-slate-500">{label}</p> : null}
    </div>
  );
}
