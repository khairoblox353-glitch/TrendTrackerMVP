import type { Metadata } from "next";

import "./globals.css";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { API_BASE_URL } from "@/lib/config";
import { getCategories, orEmpty } from "@/lib/api";
import { I18nProvider } from "@/lib/i18n";

// The server cannot read the stored locale (it lives in localStorage), so the document
// metadata stays English; only the rendered chrome switches language.
export const metadata: Metadata = {
  title: {
    default: "Trend Tracker",
    template: "%s · Trend Tracker",
  },
  description:
    "Track emerging topics across AI, Technology, Finance, Gaming and Health.",
};

/**
 * Root layout.
 *
 * The category navigation is fetched from the backend once per layout render, so the
 * header always reflects the taxonomy the API actually serves. If the backend is
 * unreachable the header degrades to the static links rather than breaking the page.
 *
 * `I18nProvider` wraps the chrome and the page so `useI18n` is available everywhere.
 * `<html lang="en">` stays the server-rendered default; the provider updates the
 * attribute at runtime once the stored locale is known.
 */
export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const categories = orEmpty(await getCategories(), []);

  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col">
        <I18nProvider>
          <Header
            categories={
              categories.length > 0
                ? categories.map((category) => ({ slug: category.slug, name: category.name }))
                : [
                    { slug: "ai", name: "AI" },
                    { slug: "technology", name: "Technology" },
                    { slug: "finance", name: "Finance" },
                    { slug: "gaming", name: "Gaming" },
                    { slug: "health", name: "Health" },
                  ]
            }
          />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">{children}</main>
          <Footer apiBaseUrl={API_BASE_URL} />
        </I18nProvider>
      </body>
    </html>
  );
}