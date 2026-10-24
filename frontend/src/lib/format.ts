import type { ResultStatus, RunStatus, Severity } from "./types";

export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];

export const RISK_CATEGORY_LABELS: Record<string, string> = {
  excessive_agency: "Excessive agency",
  prompt_injection: "Prompt injection",
  sensitive_data_exposure: "Sensitive data exposure",
  unbounded_consumption: "Unbounded consumption",
  reliability: "Reliability",
};

export function riskLabel(category: string): string {
  return RISK_CATEGORY_LABELS[category] ?? humanize(category);
}

export function humanize(value: string): string {
  const s = value.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatScore(score: number | null | undefined): string {
  return score === null || score === undefined ? "—" : `${Math.round(score)}`;
}

/** Score band used for colour + label. Thresholds are deliberately strict. */
export function scoreBand(score: number | null | undefined): "good" | "warning" | "critical" | "none" {
  if (score === null || score === undefined) return "none";
  if (score >= 90) return "good";
  if (score >= 60) return "warning";
  return "critical";
}

export function percent(part: number, total: number): number {
  return total > 0 ? Math.round((100 * part) / total) : 0;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

export function relativeTime(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "—";
  const seconds = Math.round((now.getTime() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function isActive(status: RunStatus): boolean {
  return status === "queued" || status === "running";
}

export const STATUS_LABEL: Record<ResultStatus | RunStatus, string> = {
  passed: "Passed",
  failed: "Failed",
  error: "Error",
  queued: "Queued",
  running: "Running",
  completed: "Completed",
};
