import type { AnalyzeResponse, ContentType, RedactRequest, RedactResponse } from "../types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function parse<T>(response: Response): Promise<T> {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail ?? body?.error?.message ?? `Request failed (${response.status})`);
  return body as T;
}

export async function analyze(contentType: ContentType, text?: string, file?: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("content_type", contentType);
  if (text !== undefined) form.append("text", text);
  if (file) form.append("file", file);
  return parse<AnalyzeResponse>(await fetch(`${API_BASE}/api/v1/analyze`, { method: "POST", body: form }));
}

export async function redact(payload: RedactRequest): Promise<RedactResponse> {
  return parse<RedactResponse>(await fetch(`${API_BASE}/api/v1/redact`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }));
}
