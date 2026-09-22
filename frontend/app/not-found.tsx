"use client";

import Link from "next/link";

import { useI18n } from "@/lib/i18n";

/** Global 404. Renders outside the provider on unknown routes, so `useI18n` falls back to EN. */
export default function NotFound() {
  const { t } = useI18n();

  return (
    <div className="card border-dashed py-16 text-center">
      <p className="text-4xl font-semibold text-white">404</p>
      <p className="mt-2 text-slate-400">{t.notFound.body}</p>
      <div className="mt-6 flex justify-center gap-3">
        <Link href="/" className="chip chip-active">
          {t.notFound.homepage}
        </Link>
        <Link href="/trends" className="chip">
          {t.nav.allTrends}
        </Link>
      </div>
    </div>
  );
}