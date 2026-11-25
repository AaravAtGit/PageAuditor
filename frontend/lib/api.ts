// Calls to the FastAPI backend. Types mirror backend/app/schemas.py.

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Fix = { priority: "high" | "medium" | "low"; issue: string; before: string; after: string };

export type Audit = {
  id: string;
  url: string;
  created_at: string;
  model: string;
  tokens_used: number;
  latency_ms: number;
  cached: boolean;
  report: {
    overall_score: number;
    sub_scores: Record<string, number>;
    summary: string;
    fixes: Fix[];
  };
};

export type AuditListItem = { id: string; url: string; overall_score: number; created_at: string };

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(API_URL + path, { headers: { "Content-Type": "application/json" }, ...options });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    // Our API errors are {"detail": "message"}; FastAPI validation errors have a list instead.
    throw new Error(typeof body?.detail === "string" ? body.detail : "Request failed. Check the URL and try again.");
  }
  return res.json();
}

export const createAudit = (url: string, refresh: boolean) =>
  request<Audit>(`/audits${refresh ? "?refresh=true" : ""}`, { method: "POST", body: JSON.stringify({ url }) });

export const getAudit = (id: string) => request<Audit>(`/audits/${id}`);

export const listAudits = () => request<AuditListItem[]>("/audits");
