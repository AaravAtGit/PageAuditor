"use client";

import { useEffect, useState } from "react";
import { type Audit, type AuditListItem, type Fix, createAudit, getAudit, listAudits } from "@/lib/api";

const FACTORS = [
  { key: "answerability", name: "Answer\u00ADability", color: "#2f62c9" },
  { key: "content_structure", name: "Structure", color: "#3f8a35" },
  { key: "entity_clarity", name: "Entity clarity", color: "#c9740f" },
  { key: "schema_markup", name: "Schema", color: "#6e55b8" },
  { key: "trust_signals", name: "Trust", color: "#c03a78" },
];

// client | factor | competitor; on phones the factor label takes its own line above the pair
const ROW = "grid grid-cols-2 md:grid-cols-[1fr_minmax(112px,160px)_1fr]";

type View = { kind: "single"; audit: Audit } | { kind: "compare"; client: Audit; competitor: Audit } | null;

export default function Home() {
  const [compare, setCompare] = useState(false);
  const [url, setUrl] = useState("");
  const [competitorUrl, setCompetitorUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>(null);
  const [history, setHistory] = useState<AuditListItem[]>([]);

  useEffect(() => {
    listAudits().then(setHistory).catch(() => {});
  }, []);

  async function run(load: () => Promise<View>) {
    setLoading(true);
    setError("");
    try {
      setView(await load());
      setHistory(await listAudits());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (compare) {
      run(async () => {
        const [client, competitor] = await Promise.all([
          createAudit(url).catch((e) => Promise.reject(new Error(`Client URL: ${e.message}`))),
          createAudit(competitorUrl).catch((e) => Promise.reject(new Error(`Competitor URL: ${e.message}`))),
        ]);
        return { kind: "compare", client, competitor };
      });
    } else {
      run(async () => ({ kind: "single", audit: await createAudit(url) }));
    }
  }

  function openAudit(id: string) {
    setCompare(false);
    run(async () => ({ kind: "single", audit: await getAudit(id) }));
  }

  const selectedId = view?.kind === "single" ? view.audit.id : null;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex flex-wrap items-center gap-x-6 gap-y-3 bg-ink px-6 py-3 text-paper">
        <h1 className="font-extrabold tracking-wide md:w-56">AEO Page Auditor</h1>

        <form onSubmit={onSubmit} className="flex flex-1 basis-80 flex-wrap gap-2">
          <UrlInput label={compare ? "Client page URL" : "Page URL"} value={url} onChange={setUrl} />
          {compare && <UrlInput label="Competitor URL" value={competitorUrl} onChange={setCompetitorUrl} />}
          <button
            disabled={loading}
            className="h-10 bg-accent px-6 font-semibold text-white hover:bg-[#0b5751] disabled:opacity-60"
          >
            {loading ? "Auditing…" : compare ? "Compare" : "Audit"}
          </button>
        </form>

        <div className="flex border border-[#3a4640]" role="group" aria-label="Mode">
          {["Single", "Compare"].map((label) => {
            const on = (label === "Compare") === compare;
            return (
              <button
                key={label}
                aria-pressed={on}
                onClick={() => setCompare(label === "Compare")}
                className={`h-10 px-4 text-sm ${on ? "bg-paper font-semibold text-ink" : "hover:bg-ink-soft"}`}
              >
                {label}
              </button>
            );
          })}
        </div>
      </header>

      <div className="grid flex-1 md:grid-cols-[280px_1fr]">
        <aside className="order-2 border-t border-rule md:order-1 md:border-t-0 md:border-r">
          <h2 className="px-6 pt-5 pb-3 text-xs font-semibold tracking-widest text-muted uppercase">Recent audits</h2>
          {history.length === 0 && (
            <p className="px-6 text-sm text-muted">Every audit you run is saved here so you can reopen it.</p>
          )}
          <ul>
            {history.map((item) => (
              <li key={item.id} className="border-t border-sunk">
                <button
                  onClick={() => openAudit(item.id)}
                  className={`grid w-full grid-cols-[44px_1fr] px-6 py-3 text-left hover:bg-white ${
                    item.id === selectedId ? "bg-white" : ""
                  }`}
                >
                  <span className={`text-lg font-bold ${item.id === selectedId ? "text-accent" : ""}`}>
                    {item.overall_score}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-sm">{shortUrl(item.url)}</span>
                    <span className="text-xs text-muted">{new Date(item.created_at).toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" })}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <main className="order-1 min-w-0 px-6 py-8 md:order-2 md:px-12">
          {error && (
            <p role="alert" className="mb-6 border border-danger bg-white px-4 py-3 text-danger">
              {error}
            </p>
          )}
          {loading ? (
            <Loading compare={compare} />
          ) : view?.kind === "single" ? (
            <Report audit={view.audit} />
          ) : view?.kind === "compare" ? (
            <Compare client={view.client} competitor={view.competitor} />
          ) : (
            <Empty />
          )}
        </main>
      </div>
    </div>
  );
}

function UrlInput({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <input
      type="url"
      required
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={label === "Page URL" ? "https://example.com/page" : label}
      aria-label={label}
      className="h-10 min-w-0 flex-1 basis-60 border border-ink-soft bg-ink-soft px-3 text-paper placeholder:text-[#a3ada7]"
    />
  );
}

function shortUrl(url: string) {
  return url.replace(/^https?:\/\//, "");
}

function Empty() {
  return (
    <div className="max-w-2xl">
      <h2 className="text-3xl font-bold">Audit a page for AI search</h2>
      <p className="mt-3 text-muted">
        Paste a URL above. You get a 0–100 score for how likely ChatGPT, Perplexity and Google AI Overviews are to cite
        the page, a score for each factor below, and five fixes with ready-to-use rewrites. Switch to Compare to put a
        client page next to a competitor&apos;s.
      </p>
      <ul className="mt-8 grid grid-cols-2 gap-x-0.5 gap-y-4 sm:grid-cols-5">
        {FACTORS.map((f) => (
          <li key={f.key}>
            <div className="h-2" style={{ background: f.color }} />
            <p className="mt-2 text-sm font-semibold">{f.name}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Loading({ compare }: { compare: boolean }) {
  return (
    <div aria-live="polite">
      <p className="text-sm text-muted">
        Fetching {compare ? "both pages" : "the page"}, extracting signals and scoring with Gemini. This usually takes
        5–20 seconds.
      </p>
      <div className="mt-6 grid grid-cols-5 motion-safe:animate-pulse gap-0.5">
        {FACTORS.map((f) => (
          <div key={f.key} className="h-24 bg-sunk" />
        ))}
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return <h2 className="border-b border-ink pb-2 text-sm font-semibold tracking-widest uppercase">{children}</h2>;
}

function Report({ audit }: { audit: Audit }) {
  const { report } = audit;
  return (
    <article>
      <p className="text-xs break-words text-muted">
        <a href={audit.url} target="_blank" rel="noreferrer" className="underline-offset-2 hover:underline">
          {audit.url}
        </a>{" "}
        · {new Date(audit.created_at).toLocaleString()} · {audit.model} · {audit.tokens_used.toLocaleString()} tokens
        · {(audit.latency_ms / 1000).toFixed(1)}s
      </p>

      <div className="mt-4 grid items-end gap-10 lg:grid-cols-[auto_1fr]">
        <p className="text-8xl leading-none font-extrabold tracking-[-0.04em]">
          {report.overall_score}
          <span className="text-2xl font-semibold tracking-normal text-muted">/100</span>
        </p>
        <div className="grid grid-cols-5 gap-0.5">
          {FACTORS.map((f) => {
            const score = report.sub_scores[f.key];
            return (
              <div key={f.key} className="min-w-0">
                <div className="relative h-24 bg-sunk">
                  <div
                    className="grow-up absolute inset-x-0 bottom-0"
                    style={{ height: `${score}%`, background: f.color }}
                  />
                </div>
                <p className="mt-2 text-lg leading-none font-bold">{score}</p>
                <p className="mt-1 text-xs sm:text-sm">{f.name}</p>
              </div>
            );
          })}
        </div>
      </div>

      <Fixes fixes={report.fixes} title="Top 5 fixes" />
      <Signals audit={audit} />
    </article>
  );
}

function Fixes({ fixes, title }: { fixes: Fix[]; title: string }) {
  return (
    <section className="mt-12">
      <SectionTitle>{title}</SectionTitle>
      {fixes.map((fix, i) => (
        <div key={i} className="grid gap-x-6 gap-y-3 border-b border-rule py-5 md:grid-cols-[88px_1fr_1fr]">
          <Priority value={fix.priority} />
          <p className="font-semibold md:col-span-2">{fix.issue}</p>
          <Rewrite label="Before" text={fix.before} className="bg-sunk md:col-start-2" />
          <Rewrite label="After" text={fix.after} className="border border-rule bg-white" />
        </div>
      ))}
    </section>
  );
}

function Priority({ value }: { value: Fix["priority"] }) {
  const style = { high: "bg-ink text-paper", medium: "border border-ink", low: "border border-rule text-muted" }[value];
  return (
    <span className={`h-fit w-fit px-2 py-0.5 text-xs font-semibold tracking-widest uppercase ${style}`}>{value}</span>
  );
}

function Rewrite({ label, text, className }: { label: string; text: string; className: string }) {
  return (
    <div className={`p-3 text-sm ${className}`}>
      <p className="mb-1 text-xs font-semibold tracking-widest text-muted uppercase">{label}</p>
      <p className="break-words whitespace-pre-wrap">{text}</p>
    </div>
  );
}

function signalRows(audit: Audit): [string, string][] {
  const s = audit.signals;
  return [
    ["Title", s.title ?? "(missing)"],
    ["Meta description", s.meta_description ?? "(missing)"],
    ["Canonical", s.canonical ?? "(missing)"],
    ["Word count", s.word_count.toLocaleString()],
    ["Schema types", s.schema_types.join(", ") || "(none)"],
    ["FAQ questions", String(s.faq.length)],
    ["Links", `${s.internal_links} internal, ${s.external_links} external`],
    ["Images with alt text", `${s.images_with_alt} of ${s.images}`],
  ];
}

function Signals({ audit }: { audit: Audit }) {
  const headings = audit.signals.headings;
  return (
    <section className="mt-12">
      <SectionTitle>Page signals</SectionTitle>
      <dl className="grid text-sm md:grid-cols-[200px_1fr]">
        {signalRows(audit).map(([name, value]) => (
          <div key={name} className="contents">
            <dt className="pt-2 text-muted md:border-b md:border-rule md:pb-2">{name}</dt>
            <dd className="border-b border-rule pb-2 break-words md:pt-2">{value}</dd>
          </div>
        ))}
      </dl>
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer py-1 text-muted hover:text-ink">Heading outline ({headings.length})</summary>
        <ul className="mt-2 space-y-1">
          {headings.map((h, i) => (
            <li key={i} className={h.startsWith("H1") ? "font-semibold" : h.startsWith("H3") ? "pl-8" : "pl-4"}>
              {h}
            </li>
          ))}
        </ul>
      </details>
    </section>
  );
}

function Compare({ client, competitor }: { client: Audit; competitor: Audit }) {
  const gap = client.report.overall_score - competitor.report.overall_score;
  const competitorSignals = signalRows(competitor);

  return (
    <article>
      <div className={`${ROW} items-end`}>
        <Side label="Client" audit={client} className="order-1 pr-3 text-right" />
        <p className="order-3 col-span-2 pt-6 text-center md:order-2 md:col-span-1 md:pt-0">
          <span className="block text-xs font-semibold tracking-widest text-muted uppercase">Gap</span>
          <span className="text-8xl leading-none font-extrabold tracking-[-0.04em]">{signed(gap)}</span>
        </p>
        <Side label="Competitor" audit={competitor} className="order-2 pl-3 md:order-3" />
      </div>

      <section className="mt-10 border-t border-ink">
        {FACTORS.map((f) => {
          const a = client.report.sub_scores[f.key];
          const b = competitor.report.sub_scores[f.key];
          return (
            <div key={f.key} className={`${ROW} items-center border-b border-rule py-3`}>
              <p className="order-1 col-span-2 pb-2 text-center text-sm md:order-2 md:col-span-1 md:px-3 md:pb-0">
                <span className="font-semibold">{f.name}</span>{" "}
                <span className={`md:block ${a < b ? "font-bold" : "text-muted"}`}>
                  {a === b ? "level" : a < b ? `${b - a} behind` : `${a - b} ahead`}
                </span>
              </p>
              <Bar value={a} color={f.color} side="left" />
              <Bar value={b} color={f.color} side="right" />
            </div>
          );
        })}
      </section>

      <Fixes fixes={client.report.fixes} title="Fixes for the client page" />

      <section className="mt-12">
        <SectionTitle>Page signals</SectionTitle>
        {signalRows(client).map(([name, value], i) => (
          <div key={name} className={`${ROW} border-b border-rule py-2 text-sm`}>
            <span className="order-1 col-span-2 text-center text-muted md:order-2 md:col-span-1">{name}</span>
            <span className="order-2 min-w-0 pr-3 text-right break-words md:order-1">{value}</span>
            <span className="order-3 min-w-0 pl-3 break-words">{competitorSignals[i][1]}</span>
          </div>
        ))}
      </section>
    </article>
  );
}

function signed(n: number) {
  return n > 0 ? `+${n}` : n < 0 ? `−${-n}` : "0";
}

function Side({ label, audit, className }: { label: string; audit: Audit; className: string }) {
  return (
    <div className={`min-w-0 ${className}`}>
      <p className="text-xs font-semibold tracking-widest text-muted uppercase">{label}</p>
      <p className="truncate text-sm">{shortUrl(audit.url)}</p>
      <p className="mt-2 text-6xl leading-none font-extrabold tracking-[-0.04em]">{audit.report.overall_score}</p>
    </div>
  );
}

function Bar({ value, color, side }: { value: number; color: string; side: "left" | "right" }) {
  const left = side === "left";
  return (
    <div className={`flex items-center gap-2 ${left ? "order-2 flex-row-reverse pr-3 md:order-1" : "order-3 pl-3"}`}>
      <div className={`flex h-6 flex-1 bg-sunk ${left ? "justify-end" : ""}`}>
        <div
          className={`grow-out ${left ? "origin-right" : "origin-left"}`}
          style={{ width: `${value}%`, background: color }}
        />
      </div>
      <b className="w-7 shrink-0 text-sm">{value}</b>
    </div>
  );
}
