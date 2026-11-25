"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, type AuditSummary, listAudits, scoreTone } from "@/lib/api";

export function AuditHistory() {
  const [items, setItems] = useState<AuditSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAudits(50)
      .then((res) => setItems(res.items))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load history."));
  }, []);

  if (error) return <p className="text-sm text-rose-600 dark:text-rose-400">{error}</p>;
  if (!items) return <HistorySkeleton />;
  if (items.length === 0)
    return <p className="text-sm text-neutral-500">No audits yet. Paste a URL above to run the first one.</p>;

  return (
    <ul className="divide-y divide-neutral-200 rounded-lg border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
      {items.map((a) => (
        <li key={a.id}>
          <Link
            href={`/audits/${a.id}`}
            className="flex items-center gap-4 px-4 py-3 transition hover:bg-neutral-50 dark:hover:bg-neutral-900"
          >
            <span className={`w-10 text-right text-lg font-semibold tabular-nums ${scoreTone(a.overall_score).text}`}>
              {a.overall_score}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{a.final_url}</span>
              <span className="block text-xs text-neutral-500">
                {new Date(a.created_at).toLocaleString()} · {a.model}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function HistorySkeleton() {
  return (
    <div className="space-y-2" aria-hidden>
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-14 animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-900" />
      ))}
    </div>
  );
}
