"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ApiError,
  type AuditDetail,
  type Fix,
  type Priority,
  SUB_SCORE_LABELS,
  type SubScoreName,
  getAudit,
  scoreTone,
} from "@/lib/api";

const PRIORITY_ORDER: Record<Priority, number> = { high: 0, medium: 1, low: 2 };
const PRIORITY_STYLE: Record<Priority, string> = {
  high: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  low: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
};

export function AuditReportView() {
  const { id } = useParams<{ id: string }>();
  const cachedHint = useSearchParams().get("cached") === "1";
  const [audit, setAudit] = useState<AuditDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAudit(id)
      .then(setAudit)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Could not load this audit."));
  }, [id]);

  if (error) return <p className="text-rose-600 dark:text-rose-400">{error}</p>;
  if (!audit) return <ReportSkeleton />;

  const { report, signals } = audit;
  const fixes = [...report.fixes].sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);

  return (
    <div className="space-y-10">
      <header className="space-y-2">
        <a href={audit.final_url} target="_blank" rel="noreferrer" className="break-all text-lg font-semibold hover:underline">
          {audit.final_url}
        </a>
        <p className="text-sm text-neutral-500">
          Audited {new Date(audit.created_at).toLocaleString()} · {audit.model} ·{" "}
          {(audit.input_tokens + audit.output_tokens).toLocaleString()} tokens · {(audit.latency_ms / 1000).toFixed(1)}s
          {cachedHint && " · served from the 24h cache"}
        </p>
      </header>

      <section className="grid gap-8 sm:grid-cols-[auto_1fr] sm:items-center">
        <ScoreRing score={report.overall_score} />
        <div className="space-y-3">
          {(Object.keys(SUB_SCORE_LABELS) as SubScoreName[]).map((key) => (
            <SubScoreBar key={key} label={SUB_SCORE_LABELS[key]} score={report.sub_scores[key]} />
          ))}
        </div>
      </section>

      <p className="text-neutral-700 dark:text-neutral-300">{report.summary}</p>

      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Prioritised fixes</h2>
        <ol className="space-y-4">
          {fixes.map((fix, i) => (
            <FixCard key={i} fix={fix} index={i + 1} />
          ))}
        </ol>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Extracted signals</h2>
        <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-[max-content_1fr]">
          <Signal label="Title" value={signals.title} />
          <Signal label="Meta description" value={signals.meta_description} />
          <Signal label="Canonical" value={signals.canonical} />
          <Signal label="Word count" value={signals.word_count.toLocaleString()} />
          <Signal label="Headings" value={`${signals.headings.filter((h) => h.level === 1).length} H1 · ${signals.headings.filter((h) => h.level === 2).length} H2 · ${signals.headings.filter((h) => h.level === 3).length} H3`} />
          <Signal label="JSON-LD types" value={signals.jsonld_types.join(", ") || null} />
          <Signal label="FAQ blocks" value={String(signals.faq.length)} />
          <Signal label="Links" value={`${signals.links.internal} internal · ${signals.links.external} external`} />
          <Signal
            label="Image alt text"
            value={`${Math.round(signals.images.coverage * 100)}% (${signals.images.with_alt}/${signals.images.total} images)`}
          />
        </dl>
      </section>

      <Link href="/" className="inline-block text-sm text-neutral-600 hover:underline dark:text-neutral-400">
        ← Audit another page
      </Link>
    </div>
  );
}

function ScoreRing({ score }: { score: number }) {
  const r = 52;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative mx-auto h-36 w-36" aria-label={`Overall score ${score} out of 100`}>
      <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
        <circle cx="60" cy="60" r={r} fill="none" strokeWidth="10" className="stroke-neutral-200 dark:stroke-neutral-800" />
        <circle
          cx="60" cy="60" r={r} fill="none" strokeWidth="10" strokeLinecap="round"
          stroke="currentColor" strokeDasharray={c} strokeDashoffset={c * (1 - score / 100)}
          className={scoreTone(score).text}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className={`text-4xl font-bold tabular-nums ${scoreTone(score).text}`}>{score}</span>
        <span className="text-xs text-neutral-500">out of 100</span>
      </div>
    </div>
  );
}

function SubScoreBar({ label, score }: { label: string; score: number }) {
  return (
    <div>
      <div className="mb-1 flex justify-between text-sm">
        <span>{label}</span>
        <span className="font-medium tabular-nums">{score}</span>
      </div>
      <div className="h-2 rounded-full bg-neutral-200 dark:bg-neutral-800">
        <div className={`h-2 rounded-full ${scoreTone(score).bar}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

function FixCard({ fix, index }: { fix: Fix; index: number }) {
  return (
    <li className="space-y-3 rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm text-neutral-500">{index}.</span>
        <h3 className="font-semibold">{fix.title}</h3>
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${PRIORITY_STYLE[fix.priority]}`}>{fix.priority}</span>
        <span className="text-xs text-neutral-500">{SUB_SCORE_LABELS[fix.category]}</span>
      </div>
      <p className="text-sm text-neutral-700 dark:text-neutral-300">{fix.issue}</p>
      <div className="grid gap-3 md:grid-cols-2">
        <Snippet label="Before" text={fix.before} tone="before" />
        <Snippet label="After" text={fix.after} tone="after" />
      </div>
    </li>
  );
}

function Snippet({ label, text, tone }: { label: string; text: string; tone: "before" | "after" }) {
  const style =
    tone === "before"
      ? "border-rose-200 bg-rose-50/50 dark:border-rose-900 dark:bg-rose-950/30"
      : "border-emerald-200 bg-emerald-50/50 dark:border-emerald-900 dark:bg-emerald-950/30";
  return (
    <div className={`min-w-0 rounded-md border p-3 ${style}`}>
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-neutral-500">{label}</div>
      <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">{text}</pre>
    </div>
  );
}

function Signal({ label, value }: { label: string; value: string | null }) {
  return (
    <>
      <dt className="text-neutral-500">{label}</dt>
      <dd className="break-words">{value ?? <span className="text-rose-600 dark:text-rose-400">missing</span>}</dd>
    </>
  );
}

function ReportSkeleton() {
  return (
    <div className="space-y-6" aria-hidden>
      <div className="h-6 w-2/3 animate-pulse rounded bg-neutral-100 dark:bg-neutral-900" />
      <div className="h-36 animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-900" />
      <div className="h-48 animate-pulse rounded-lg bg-neutral-100 dark:bg-neutral-900" />
    </div>
  );
}
