"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, createAudit } from "@/lib/api";

// The backend does this as one request, so these steps are paced by elapsed time,
// not reported by the server. (Real progress is the "streaming" stretch goal.)
const STEPS = [
  { after: 0, label: "Fetching the page…" },
  { after: 3, label: "Extracting on-page signals…" },
  { after: 6, label: "Scoring with the LLM…" },
];

export function AuditForm() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [refresh, setRefresh] = useState(false);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 500);
    return () => clearInterval(timer);
  }, [loading]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    let target = url.trim();
    if (!target) return;
    if (!/^https?:\/\//i.test(target)) target = `https://${target}`;

    setError(null);
    setElapsed(0);
    setLoading(true);
    try {
      const audit = await createAudit(target, refresh);
      router.push(`/audits/${audit.id}${audit.cached ? "?cached=1" : ""}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
      setLoading(false);
    }
  }

  const step = [...STEPS].reverse().find((s) => elapsed >= s.after)!;

  return (
    <form onSubmit={onSubmit} className="space-y-3">
      <div className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="url" className="sr-only">
          Page URL
        </label>
        <input
          id="url"
          type="text"
          inputMode="url"
          autoComplete="url"
          placeholder="https://example.com/page"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          disabled={loading}
          className="flex-1 rounded-lg border border-neutral-300 bg-white px-4 py-3 text-base outline-none focus:border-neutral-900 focus:ring-2 focus:ring-neutral-900/10 disabled:opacity-60 dark:border-neutral-700 dark:bg-neutral-900 dark:focus:border-neutral-300"
        />
        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="rounded-lg bg-neutral-900 px-6 py-3 font-medium text-white transition hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-200"
        >
          {loading ? "Auditing…" : "Audit page"}
        </button>
      </div>

      <label className="flex w-fit items-center gap-2 text-sm text-neutral-600 dark:text-neutral-400">
        <input
          type="checkbox"
          checked={refresh}
          onChange={(e) => setRefresh(e.target.checked)}
          disabled={loading}
        />
        Ignore the 24-hour cache and re-audit
      </label>

      {loading && (
        <div
          role="status"
          className="flex items-center gap-3 rounded-lg border border-neutral-200 px-4 py-3 text-sm dark:border-neutral-800"
        >
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-neutral-300 border-t-neutral-900 dark:border-neutral-700 dark:border-t-white" />
          <span>{step.label}</span>
          <span className="ml-auto tabular-nums text-neutral-500">{elapsed}s</span>
        </div>
      )}

      {error && (
        <p role="alert" className="rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700 dark:bg-rose-950/50 dark:text-rose-300">
          {error}
        </p>
      )}
    </form>
  );
}
