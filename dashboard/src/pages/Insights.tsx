import type { ReactNode } from "react";
import {
  api,
  type ClaimWork,
  type DecisionKind,
  type InsightTotals,
  type Insights,
} from "../api";
import {
  ClaimType,
  DecisionBadge,
  ErrorNote,
  Loading,
  Panel,
  StatusBadge,
} from "../components/elements";
import { DECISION_LABELS, duration, money, percent } from "../format";
import { usePoll } from "../hooks";
import { Timeline } from "../components/Timeline";
import { paths } from "../paths";

const DECISIONS: DecisionKind[] = ["approve", "decline", "refer"];

const DECISION_TONES = DECISIONS.map((decision) => ({
  tone: decision,
  label: DECISION_LABELS[decision],
}));

export interface Segment {
  tone: string;
  label: string;
  value: number;
}

export interface BarRow {
  key: string;
  label: ReactNode;
  segments: Segment[];
  note: string;
}

function total(row: BarRow): number {
  return row.segments.reduce((sum, segment) => sum + segment.value, 0);
}

function width(value: number, max: number): string {
  return `${String((value / max) * 100)}%`;
}

export function Bars({
  rows,
  label,
}: Readonly<{ rows: BarRow[]; label: string }>) {
  const max = Math.max(1, ...rows.map(total));
  return (
    <ul className="bars" aria-label={label}>
      {rows.map((row) => (
        <li key={row.key}>
          <span className="bars__label">{row.label}</span>
          <span className="bar">
            {row.segments
              .filter((segment) => segment.value > 0)
              .map((segment) => (
                <span
                  key={segment.label}
                  className={`bar__segment tone--${segment.tone}`}
                  style={{ width: width(segment.value, max) }}
                  title={`${segment.label}: ${String(segment.value)}`}
                  aria-label={`${segment.label}: ${String(segment.value)}`}
                >
                  {segment.value}
                </span>
              ))}
          </span>
          <span className="bars__note">{row.note}</span>
        </li>
      ))}
    </ul>
  );
}

function Legend({
  items,
}: Readonly<{ items: { tone: string; label: string }[] }>) {
  return (
    <ul className="legend">
      {items.map((item) => (
        <li key={item.tone} className={`tone--${item.tone}`}>
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function plural(count: number, word: string): string {
  return `${String(count)} ${word}${count === 1 ? "" : "s"}`;
}

function Stats({ totals }: Readonly<{ totals: InsightTotals }>) {
  const median = totals.median_seconds;
  const longest = totals.longest_seconds;
  return (
    <dl className="stat-tiles">
      <div>
        <dt>Straight through</dt>
        <dd>{percent(totals.straight_through, totals.decided)}</dd>
        <dd className="stat-tiles__note">
          {totals.straight_through} of {plural(totals.decided, "claim")}{" "}
          decided, with no handler
        </dd>
      </div>
      <div>
        <dt>Time per claim</dt>
        <dd>{median === null ? "—" : duration(median)}</dd>
        <dd className="stat-tiles__note">
          {longest === null
            ? "No runs yet"
            : `Median; longest ${duration(longest)}`}
        </dd>
      </div>
      <div>
        <dt>Tool calls</dt>
        <dd>{totals.tool_calls}</dd>
        <dd className="stat-tiles__note">
          {totals.refused} refused by the backend
        </dd>
      </div>
      <div>
        <dt>Waiting for a handler</dt>
        <dd>{totals.waiting_for_handler}</dd>
        <dd className="stat-tiles__note">
          {plural(totals.sign_offs, "sign-off")} and{" "}
          {plural(totals.referred, "referral")} so far
        </dd>
      </div>
    </dl>
  );
}

function Money({ totals }: Readonly<{ totals: InsightTotals }>) {
  return (
    <dl className="money-tiles">
      <div>
        <dt>Claimed on decided claims</dt>
        <dd>{money(totals.claimed)}</dd>
      </div>
      <div>
        <dt>Approved by the agent</dt>
        <dd>{money(totals.approved)}</dd>
      </div>
      <div>
        <dt>Paid out</dt>
        <dd>{money(totals.paid)}</dd>
      </div>
      <div>
        <dt>Held for sign-off</dt>
        <dd>{money(totals.held)}</dd>
      </div>
    </dl>
  );
}

function ClaimTable({ claims }: Readonly<{ claims: ClaimWork[] }>) {
  return (
    <div className="table-scroll">
      <table className="queue-table">
        <thead>
          <tr>
            <th>Claim</th>
            <th>Type</th>
            <th>Agent's decision</th>
            <th>State</th>
            <th className="numeric">Time</th>
            <th className="numeric">Tool calls</th>
            <th className="numeric">Refused</th>
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.claim_id}>
              <td>
                <a className="mono" href={paths.claim(claim.claim_id)}>
                  {claim.claim_id}
                </a>
              </td>
              <td>
                <ClaimType type={claim.claim_type} />
              </td>
              <td>
                {claim.decision ? (
                  <DecisionBadge decision={claim.decision} />
                ) : (
                  <span className="muted">—</span>
                )}
              </td>
              <td>
                <StatusBadge status={claim.status} />
              </td>
              <td className="numeric mono">{duration(claim.seconds)}</td>
              <td className="numeric mono">{claim.tool_calls}</td>
              <td className="numeric mono">{claim.refused}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Report({ insights }: Readonly<{ insights: Insights }>) {
  const byType: BarRow[] = insights.by_type.map((mix) => ({
    key: mix.claim_type,
    label: <ClaimType type={mix.claim_type} />,
    segments: DECISIONS.map((decision) => ({
      tone: decision,
      label: DECISION_LABELS[decision],
      value: mix[decision],
    })),
    note: String(mix.approve + mix.decline + mix.refer),
  }));
  const tools: BarRow[] = insights.tools.map((tool) => ({
    key: tool.tool,
    label: <span className="mono">{tool.tool}</span>,
    segments: [
      { tone: "calls", label: "Answered", value: tool.calls - tool.refused },
      { tone: "refused", label: "Refused", value: tool.refused },
    ],
    note: String(tool.calls),
  }));
  const sections: BarRow[] = insights.sections.map((section) => ({
    key: section.section,
    label: section.section,
    segments: [{ tone: "calls", label: "Claims", value: section.claims }],
    note: String(section.claims),
  }));

  return (
    <>
      <Stats totals={insights.totals} />
      <Money totals={insights.totals} />
      {insights.claims.length > 0 && (
        <Panel title="The latest run">
          <Legend items={DECISION_TONES} />
          <Timeline claims={insights.claims} />
        </Panel>
      )}
      <Panel title="The agent's decisions by claim type">
        <Legend items={DECISION_TONES} />
        <Bars rows={byType} label="Decisions by claim type" />
      </Panel>
      <div className="insights-grid">
        <Panel title="Tools the agent called">
          <Legend
            items={[
              { tone: "calls", label: "Answered" },
              { tone: "refused", label: "Refused by the backend" },
            ]}
          />
          <Bars rows={tools} label="Tool calls" />
        </Panel>
        <Panel title="Policy sections cited">
          <Bars rows={sections} label="Policy sections cited" />
        </Panel>
      </div>
      <Panel title="Claims the agent worked">
        <ClaimTable claims={insights.claims} />
      </Panel>
    </>
  );
}

function worked(insights: Insights): boolean {
  return insights.claims.length > 0 || insights.totals.decided > 0;
}

export function InsightsPage() {
  const insights = usePoll(api.getInsights, 5000);
  const data = insights.data;

  return (
    <div className="page">
      <p className="lede">
        How the agent's work on the queue adds up, from its decisions, its steps
        and the payments.
      </p>
      {insights.error && (
        <ErrorNote message={insights.error} onRetry={insights.reload} />
      )}
      {data === null && !insights.error && (
        <Loading label="Adding up the agent's work" />
      )}
      {data !== null && !worked(data) && (
        <p className="empty">
          The agent hasn't worked a claim yet. Run it from the{" "}
          <a href={paths.queue}>queue</a>, and its work adds up here.
        </p>
      )}
      {data !== null && worked(data) && <Report insights={data} />}
    </div>
  );
}
