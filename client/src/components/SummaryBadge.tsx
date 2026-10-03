import type { AnalyzeSummary } from "../types/api";

export function SummaryBadge({ summary }: { summary: AnalyzeSummary | null }) {
  return <aside aria-label="Privacy risk summary"><strong>{summary?.risk_score ?? "WAITING"}</strong><span>{summary?.total_pii_found ?? 0} findings</span></aside>;
}
