import Link from "next/link";
import type { ReactNode } from "react";
import { formatScore, scoreBand, SEVERITIES, STATUS_LABEL } from "@/lib/format";
import type { ResultStatus, RunStatus, Severity } from "@/lib/types";

export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <section className={cx("rounded-xl border border-border bg-surface p-5", className)}>{children}</section>;
}

export function CardTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <h2 className="text-sm font-semibold text-ink">{children}</h2>
      {action}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

type Tone = "good" | "warning" | "serious" | "critical" | "neutral" | "accent";

const TONE_DOT: Record<Tone, string> = {
  good: "bg-good",
  warning: "bg-warning !text-black",
  serious: "bg-serious",
  critical: "bg-critical",
  neutral: "bg-ink-3",
  accent: "bg-accent",
};

const TONE_ICON: Record<Tone, string> = {
  good: "✓",
  warning: "!",
  serious: "!",
  critical: "✕",
  neutral: "•",
  accent: "•",
};

/** A status pill: coloured icon carries the state, text stays in ink colours. */
export function Pill({ tone, children, title }: { tone: Tone; children: ReactNode; title?: string }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border border-border bg-surface-2 px-2 py-0.5 text-xs font-medium text-ink"
    >
      <span
        aria-hidden
        className={cx("flex h-3.5 w-3.5 items-center justify-center rounded-full text-[9px] font-bold text-white", TONE_DOT[tone])}
      >
        {TONE_ICON[tone]}
      </span>
      {children}
    </span>
  );
}

const SEVERITY_TONE: Record<Severity, Tone> = {
  critical: "critical",
  high: "serious",
  medium: "warning",
  low: "neutral",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return <Pill tone={SEVERITY_TONE[severity]}>{severity.charAt(0).toUpperCase() + severity.slice(1)}</Pill>;
}

const STATUS_TONE: Record<ResultStatus | RunStatus, Tone> = {
  passed: "good",
  failed: "critical",
  error: "warning",
  queued: "neutral",
  running: "accent",
  completed: "good",
};

export function StatusBadge({ status }: { status: ResultStatus | RunStatus }) {
  return <Pill tone={STATUS_TONE[status]}>{STATUS_LABEL[status]}</Pill>;
}

const BAND_LABEL = { good: "Strong", warning: "Needs work", critical: "At risk", none: "No data" } as const;
const BAND_TONE: Record<keyof typeof BAND_LABEL, Tone> = {
  good: "good",
  warning: "warning",
  critical: "critical",
  none: "neutral",
};

export function ScoreBadge({ score }: { score: number | null | undefined }) {
  const band = scoreBand(score);
  return (
    <span className="inline-flex items-center gap-2">
      <span className="tabular text-base font-semibold text-ink">{formatScore(score)}</span>
      <Pill tone={BAND_TONE[band]}>{BAND_LABEL[band]}</Pill>
    </span>
  );
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-ink-3">{label}</div>
      <div className="tabular mt-2 text-3xl font-semibold text-ink">{value}</div>
      {hint && <div className="mt-1 text-xs text-ink-2">{hint}</div>}
    </Card>
  );
}

/** Horizontal meter: one series, one hue, on a recessive track. */
export function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = max > 0 ? Math.min(100, (100 * value) / max) : 0;
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-valuenow={value}
      title={`${label}: ${value} of ${max}`}
      className="h-2 w-full overflow-hidden rounded-full bg-track"
    >
      <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function SeverityCounts({ counts }: { counts: Partial<Record<Severity, number>> }) {
  return (
    <div className="flex flex-wrap gap-2">
      {SEVERITIES.map((s) => (
        <span key={s} className="inline-flex items-center gap-1.5">
          <SeverityBadge severity={s} />
          <span className="tabular text-sm font-semibold text-ink">{counts[s] ?? 0}</span>
        </span>
      ))}
    </div>
  );
}

export function Button({
  children,
  variant = "primary",
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "danger" }) {
  return (
    <button
      {...props}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        variant === "primary" && "bg-accent text-white hover:bg-accent-strong",
        variant === "secondary" && "border border-border bg-surface text-ink hover:bg-surface-2",
        variant === "danger" && "border border-border bg-surface text-critical hover:bg-surface-2",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function ButtonLink({ href, children, variant = "primary" }: { href: string; children: ReactNode; variant?: "primary" | "secondary" }) {
  return (
    <Link
      href={href}
      className={cx(
        "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition",
        variant === "primary" ? "bg-accent text-white hover:bg-accent-strong" : "border border-border bg-surface text-ink hover:bg-surface-2",
      )}
    >
      {children}
    </Link>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="mb-4 flex items-start gap-2 rounded-lg border border-border bg-surface p-3 text-sm text-ink">
      <Pill tone="critical">Error</Pill>
      <span>{message}</span>
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-ink-2" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-track border-t-accent" />
      {label}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-border p-8 text-center">
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="mt-2 text-sm text-ink-2">{children}</div>}
    </div>
  );
}

export function Disclaimer({ text }: { text?: string }) {
  return (
    <p className="rounded-lg border border-border bg-surface-2 p-3 text-xs leading-relaxed text-ink-2">
      <strong className="text-ink">Testing is not a guarantee.</strong>{" "}
      {text ??
        "Passing these scenarios does not prove an agent is secure. Results cover only the scenarios run, in a simulated sandbox, on that run."}
    </p>
  );
}

export const inputClass =
  "w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-ink placeholder:text-ink-3 focus:border-accent focus:outline-none";

export function Field({ label, hint, children, htmlFor }: { label: string; hint?: ReactNode; children: ReactNode; htmlFor?: string }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-ink-3">{hint}</p>}
    </div>
  );
}
