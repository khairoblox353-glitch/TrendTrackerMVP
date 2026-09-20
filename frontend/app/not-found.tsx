import Link from "next/link";

export default function NotFound() {
  return (
    <div className="card border-dashed py-16 text-center">
      <p className="text-4xl font-semibold text-white">404</p>
      <p className="mt-2 text-slate-400">This page does not exist.</p>
      <div className="mt-6 flex justify-center gap-3">
        <Link href="/" className="chip chip-active">
          Homepage
        </Link>
        <Link href="/trends" className="chip">
          All trends
        </Link>
      </div>
    </div>
  );
}
