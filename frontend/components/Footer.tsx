"use client";

import { useI18n } from "@/lib/i18n";

/** Site footer with a link to the API docs. */
export function Footer({ apiBaseUrl }: { apiBaseUrl: string }) {
  const { t } = useI18n();

  return (
    <footer className="mt-16 border-t border-white/5 py-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
        <p>{t.footer.tagline}</p>
        <p>
          {t.footer.dataVia}{" "}
          <a
            href={`${apiBaseUrl}/docs`}
            className="text-accent-soft hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            {t.footer.backend}
          </a>
          .
        </p>
      </div>
    </footer>
  );
}