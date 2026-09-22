"use client";

/**
 * EN/VI switch for the header.
 *
 * The labels are language codes, not words, so they are never translated: a Vietnamese
 * speaker who wants English must still recognise "EN". Reuses the existing `.chip` /
 * `.chip-active` classes from `app/globals.css`.
 */

import { useI18n } from "@/lib/i18n";
import type { Locale } from "@/lib/i18n";

const LOCALES: Locale[] = ["en", "vi"];

export function LocaleToggle() {
  const { locale, setLocale, t } = useI18n();

  return (
    <div
      role="group"
      aria-label={t.nav.languageLabel}
      className="flex items-center gap-1"
    >
      {LOCALES.map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => setLocale(code)}
          aria-pressed={locale === code}
          className={locale === code ? "chip chip-active text-xs px-2" : "chip text-xs px-2"}
        >
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  );
}