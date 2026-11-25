"use client";

import { useEffect, useState } from "react";
import { type Audit, type AuditListItem, createAudit, getAudit, listAudits } from "@/lib/api";

export default function Home() {
  const [url, setUrl] = useState("");
  const [refresh, setRefresh] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [audit, setAudit] = useState<Audit | null>(null);
  const [history, setHistory] = useState<AuditListItem[]>([]);

  useEffect(() => {
    listAudits().then(setHistory).catch(() => {});
  }, []);

  async function run(load: () => Promise<Audit>) {
    setLoading(true);
    setError("");
    try {
      setAudit(await load());
      setHistory(await listAudits());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const fullUrl = url.startsWith("http") ? url : `https://${url}`;
    run(() => createAudit(fullUrl, refresh));
  }

  return (
    <main className="mx-auto max-w-3xl space-y-10 px-4 py-12">
      <header>
        <h1 className="text-3xl font-bold">AEO Page Auditor</h1>
        <p className="mt-2 text-neutral-500">
          How likely is a page to be cited by ChatGPT, Perplexity and Google AI Overviews?
        </p>
      </header>

      <form onSubmit={onSubmit} className="space-y-2">
        <div className="flex gap-2">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com/page"
            className="flex-1 rounded border border-neutral-300 px-3 py-2 dark:border-neutral-700 dark:bg-neutral-900"
          />
          <button
            disabled={loading || !url}
            className="rounded bg-black px-5 py-2 text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            {loading ? "Auditing…" : "Audit"}
          </button>
        </div>
        <label className="flex items-center gap-2 text-sm text-neutral-500">
          <input type="checkbox" checked={refresh} onChange={(e) => setRefresh(e.target.checked)} />
          Re-audit even if checked in the last 24 hours
        </label>
        {loading && <p className="text-sm">Fetching, extracting and scoring… this can take up to a minute.</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </form>

      {audit && <Report audit={audit} />}

      <section>
        <h2 className="mb-2 text-xl font-semibold">History</h2>
        {history.length === 0 && <p className="text-sm text-neutral-500">No audits yet.</p>}
        <ul className="divide-y divide-neutral-200 dark:divide-neutral-800">
          {history.map((item) => (
            <li key={item.id}>
              <button onClick={() => run(() => getAudit(item.id))} className="flex w-full gap-4 py-2 text-left hover:underline">
                <span className="w-8 font-semibold">{item.overall_score}</span>
                <span className="flex-1 truncate">{item.url}</span>
                <span className="text-sm text-neutral-500">{new Date(item.created_at).toLocaleDateString()}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 };

function Report({ audit }: { audit: Audit }) {
  const { report } = audit;
  const fixes = [...report.fixes].sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);

  return (
    <section className="space-y-6 rounded border border-neutral-200 p-6 dark:border-neutral-800">
      <div>
        <p className="truncate text-sm text-neutral-500">
          {audit.url} · {audit.model} · {audit.tokens_used} tokens · {(audit.latency_ms / 1000).toFixed(1)}s
          {audit.cached && " · cached"}
        </p>
        <p className="mt-2 text-5xl font-bold">
          {report.overall_score}
          <span className="text-xl text-neutral-400">/100</span>
        </p>
        <p className="mt-2">{report.summary}</p>
      </div>

      <div className="space-y-2">
        {Object.entries(report.sub_scores).map(([name, score]) => (
          <div key={name}>
            <div className="flex justify-between text-sm capitalize">
              <span>{name.replace("_", " ")}</span>
              <span>{score}</span>
            </div>
            <div className="h-2 rounded bg-neutral-200 dark:bg-neutral-800">
              <div className="h-2 rounded bg-black dark:bg-white" style={{ width: `${score}%` }} />
            </div>
          </div>
        ))}
      </div>

      <div className="space-y-4">
        <h3 className="text-lg font-semibold">Top fixes</h3>
        {fixes.map((fix, i) => (
          <div key={i} className="space-y-2">
            <p>
              <span className="mr-2 rounded bg-neutral-200 px-2 py-0.5 text-xs uppercase dark:bg-neutral-800">
                {fix.priority}
              </span>
              {fix.issue}
            </p>
            <pre className="whitespace-pre-wrap rounded bg-red-50 p-2 text-sm dark:bg-red-950/40">Before: {fix.before}</pre>
            <pre className="whitespace-pre-wrap rounded bg-green-50 p-2 text-sm dark:bg-green-950/40">After: {fix.after}</pre>
          </div>
        ))}
      </div>
    </section>
  );
}
