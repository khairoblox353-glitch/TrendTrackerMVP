"use client";

import { ErrorState } from "@/components/ErrorState";

/** Route-level error boundary. Renders the API message when one is available. */
export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="space-y-4">
      <ErrorState
        title="Could not load this page"
        message={error.message}
        hint="The backend may be starting up. Retry in a moment."
      />
      <button
        type="button"
        onClick={reset}
        className="chip"
      >
        Try again
      </button>
    </div>
  );
}
