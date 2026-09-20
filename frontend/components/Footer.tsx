/** Site footer with a link to the API docs. */
export function Footer({ apiBaseUrl }: { apiBaseUrl: string }) {
  return (
    <footer className="mt-16 border-t border-white/5 py-8">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
        <p>Trend Tracker MVP — RSS ingestion, topic classification and trend scoring.</p>
        <p>
          Data via the{" "}
          <a
            href={`${apiBaseUrl}/docs`}
            className="text-accent-soft hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            FastAPI backend
          </a>
          .
        </p>
      </div>
    </footer>
  );
}
