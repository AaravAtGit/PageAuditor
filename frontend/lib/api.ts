// Typed client for the FastAPI backend. Types mirror backend/app/schemas.py.

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type SubScoreName =
  | "answerability"
  | "content_structure"
  | "entity_clarity"
  | "schema_markup"
  | "trust_signals";

export type Priority = "high" | "medium" | "low";

export interface Fix {
  priority: Priority;
  category: SubScoreName;
  title: string;
  issue: string;
  before: string;
  after: string;
}

export interface AuditReport {
  overall_score: number;
  sub_scores: Record<SubScoreName, number>;
  summary: string;
  fixes: Fix[];
}

export interface Signals {
  title: string | null;
  meta_description: string | null;
  canonical: string | null;
  headings: { level: 1 | 2 | 3; text: string }[];
  word_count: number;
  jsonld_types: string[];
  jsonld_invalid_blocks: number;
  faq: { question: string; answer: string; source: string }[];
  links: { internal: number; external: number };
  images: { total: number; with_alt: number; empty_alt: number; missing_alt: number; coverage: number };
  lang: string | null;
  lead_excerpt: string;
}

export interface AuditSummary {
  id: string;
  url: string;
  final_url: string;
  overall_score: number;
  model: string;
  created_at: string;
}

export interface AuditDetail extends AuditSummary {
  signals: Signals;
  report: AuditReport;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  llm_latency_ms: number;
  cached: boolean;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "network", "Could not reach the audit API. Is the backend running?");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    // Our errors are {code, message}; FastAPI's validation errors are a list.
    if (detail && typeof detail === "object" && "message" in detail) {
      throw new ApiError(res.status, detail.code, detail.message);
    }
    if (Array.isArray(detail)) {
      throw new ApiError(res.status, "validation", "Please enter a valid http(s) URL.");
    }
    throw new ApiError(res.status, "unknown", `Request failed (${res.status}).`);
  }
  return res.json() as Promise<T>;
}

export function createAudit(url: string, refresh = false) {
  return request<AuditDetail>(`/audits${refresh ? "?refresh=true" : ""}`, {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function listAudits(limit = 20, offset = 0) {
  return request<{ items: AuditSummary[]; total: number }>(`/audits?limit=${limit}&offset=${offset}`);
}

export function getAudit(id: string) {
  return request<AuditDetail>(`/audits/${encodeURIComponent(id)}`);
}

export const SUB_SCORE_LABELS: Record<SubScoreName, string> = {
  answerability: "Answerability",
  content_structure: "Content structure",
  entity_clarity: "Entity clarity",
  schema_markup: "Schema markup",
  trust_signals: "Trust signals",
};

export function scoreTone(score: number) {
  if (score >= 70) return { text: "text-emerald-600 dark:text-emerald-400", bar: "bg-emerald-500" };
  if (score >= 40) return { text: "text-amber-600 dark:text-amber-400", bar: "bg-amber-500" };
  return { text: "text-rose-600 dark:text-rose-400", bar: "bg-rose-500" };
}
