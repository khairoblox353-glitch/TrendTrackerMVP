"use client";

import { ErrorState } from "@/components/ErrorState";
import { useI18n } from "@/lib/i18n";

/** Route-level error boundary. Renders the API message when one is available. */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useI18n();

  return (
    <div className="space-y-4">
      <ErrorState
        title={t.errorPage.title}
        message={error.message}
        hint={t.errorPage.hint}
      />
      <button
        type="button"
        onClick={reset}
        className="chip"
      >
        {t.common.tryAgain}
      </button>
    </div>
  );
}