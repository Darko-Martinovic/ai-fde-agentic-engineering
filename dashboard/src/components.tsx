import type { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ClaimStatus, DecisionKind } from "./api";
import { DECISION_LABELS, STATUS_LABELS, humanize } from "./format";

export function StatusBadge({ status }: Readonly<{ status: ClaimStatus }>) {
  return (
    <span className={`badge badge--${status}`}>{STATUS_LABELS[status]}</span>
  );
}

export function DecisionBadge({
  decision,
}: Readonly<{ decision: DecisionKind }>) {
  return (
    <span className={`badge badge--${decision}`}>
      {DECISION_LABELS[decision]}
    </span>
  );
}

const ICONS: Record<string, ReactNode> = {
  trip_delay: (
    <>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  baggage: (
    <>
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <path d="M9 8V5h6v3M4 13h16" />
    </>
  ),
  baggage_delay: (
    <>
      <rect x="3" y="9" width="12" height="11" rx="2" />
      <path d="M7 9V6h4v3" />
      <circle cx="18" cy="7" r="3.5" />
      <path d="M18 5.5V7l1 1" />
    </>
  ),
  emergency_medical: <path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6z" />,
  passport: (
    <>
      <rect x="5" y="3" width="14" height="18" rx="2" />
      <circle cx="12" cy="10" r="3" />
      <path d="M9 16h6" />
    </>
  ),
  trip_cancellation: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M3 10h18M8 3v4M16 3v4M9.5 13.5l5 5M14.5 13.5l-5 5" />
    </>
  ),
  trip_interruption: (
    <>
      <path d="M3 17c4 0 4-10 9-10s5 10 9 10" />
      <path d="M10 4l4 6M14 4l-4 6" />
    </>
  ),
};

export function TypeIcon({ type }: Readonly<{ type: string }>) {
  return (
    <svg
      className={`type-icon type-icon--${type}`}
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      {ICONS[type] ?? <circle cx="12" cy="12" r="8" />}
    </svg>
  );
}

export function ClaimType({ type }: Readonly<{ type: string }>) {
  return (
    <span className="claim-type">
      <TypeIcon type={type} />
      {humanize(type)}
    </span>
  );
}

export function Panel({
  title,
  children,
  className = "",
  actions,
}: Readonly<{
  title?: string;
  children: ReactNode;
  className?: string;
  actions?: ReactNode;
}>) {
  return (
    <section className={`panel ${className}`}>
      {title && (
        <header className="panel__header">
          <h2>{title}</h2>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function ErrorNote({
  message,
  onRetry,
}: Readonly<{
  message: string;
  onRetry?: () => void;
}>) {
  return (
    <div className="note note--error" role="alert">
      <span>{message}</span>
      {onRetry && (
        <button
          type="button"
          className="button button--quiet"
          onClick={onRetry}
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function Loading({ label }: Readonly<{ label: string }>) {
  return (
    <div className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function Markdown({ text }: Readonly<{ text: string }>) {
  return (
    <div className="markdown">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}

export function Logo() {
  return (
    <svg className="logo" viewBox="0 0 40 40" aria-hidden="true">
      <path d="M6 22a14 14 0 0 1 28 0Z" fill="var(--coral)" />
      <circle cx="20" cy="24" r="9" fill="var(--sea-green)" />
      <circle cx="16.5" cy="23" r="3" fill="var(--midnight)" />
      <circle cx="23.5" cy="23" r="3" fill="var(--midnight)" />
      <path
        d="M14 8l3 5M26 8l-3 5"
        stroke="var(--sea-green)"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}
