"use client";

/**
 * Locale provider for the EN/VI toggle.
 *
 * The server always renders English: it cannot read `localStorage`, and reading a cookie
 * would force every route to become dynamic. The stored choice is therefore applied in a
 * mount effect, after hydration. That is also why the state starts at `DEFAULT_LOCALE` -
 * the first client render must match the server HTML exactly, otherwise React reports a
 * hydration mismatch.
 *
 * Because switching happens on the client, the whole `en` + `vi` dictionary ships to the
 * browser. At this size (a few hundred short strings) that is cheaper than an async
 * loading layer, extra route segments or a server round trip.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReactNode } from "react";

import { en, vi } from "./dictionary";
import type { Dictionary, Locale } from "./dictionary";

export type { Locale };

/** English is the server-rendered default, so it is also the initial client state. */
export const DEFAULT_LOCALE: Locale = "en";

export const LOCALE_STORAGE_KEY = "trend-tracker.locale";

export const DICTIONARIES: Record<Locale, Dictionary> = { en, vi };

export type I18nContextValue = {
  locale: Locale;
  setLocale: (next: Locale) => void;
  t: Dictionary;
};

/** Narrow an arbitrary stored string to a known locale, rejecting corrupt values. */
function isLocale(value: string | null): value is Locale {
  return value === "en" || value === "vi";
}

/**
 * Fallback used when a component renders outside the provider.
 *
 * Root `not-found.tsx` and error boundaries can render outside the provider, and throwing
 * there would break the 404 page itself. Returning English is harmless and keeps those
 * pages working.
 */
const noop = () => {};

const FALLBACK: I18nContextValue = {
  locale: DEFAULT_LOCALE,
  setLocale: noop,
  t: en,
};

const I18nContext = createContext<I18nContextValue>(FALLBACK);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
      if (isLocale(stored)) {
        setLocaleState(stored);
      }
    } catch {
      // localStorage throws in private mode / when storage is disabled; keep the default.
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, next);
    } catch {
      // Storage can throw in private mode; the in-memory locale is still switched.
    }
  }, []);

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t: DICTIONARIES[locale] }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/** Read the active locale and dictionary. Safe to call outside the provider. */
export function useI18n(): I18nContextValue {
  return useContext(I18nContext);
}