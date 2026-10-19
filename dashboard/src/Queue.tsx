import { useMemo, useState } from "react";
import { AgentBar } from "./AgentBar";
import { api, type ClaimStatus, type ClaimSummary } from "./api";
import {
  ClaimType,
  DecisionBadge,
  ErrorNote,
  Loading,
  StatusBadge,
} from "./components";
import { STATUSES, STATUS_LABELS, date, humanize, money } from "./format";
import { usePoll } from "./hooks";
import {
  type Filters,
  type Sort,
  type SortKey,
  claimTypes,
  countByStatus,
  filterClaims,
  sortClaims,
  totals,
} from "./filters";

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "claim_id", label: "Claim" },
  { key: "claim_type", label: "Type" },
  { key: "customer_name", label: "Customer" },
  { key: "submitted_on", label: "Submitted" },
  { key: "amount_claimed", label: "Claimed", numeric: true },
  { key: "payout", label: "Payout", numeric: true },
  { key: "status", label: "State" },
];

function StatusTiles({
  claims,
  selected,
  onSelect,
}: Readonly<{
  claims: ClaimSummary[];
  selected: ClaimStatus | "all";
  onSelect: (status: ClaimStatus | "all") => void;
}>) {
  const counts = countByStatus(claims);
  return (
    <div className="tiles" role="group" aria-label="Filter by state">
      {STATUSES.map((status) => (
        <button
          type="button"
          key={status}
          className={`tile tile--${status}`}
          aria-pressed={selected === status}
          onClick={() => {
            onSelect(selected === status ? "all" : status);
          }}
        >
          <span className="tile__count">{counts[status]}</span>
          <span className="tile__label">{STATUS_LABELS[status]}</span>
        </button>
      ))}
    </div>
  );
}

function MoneyTiles({ claims }: Readonly<{ claims: ClaimSummary[] }>) {
  const sums = totals(claims);
  return (
    <dl className="money-tiles">
      <div>
        <dt>Claimed</dt>
        <dd>{money(sums.claimed)}</dd>
      </div>
      <div>
        <dt>Paid out</dt>
        <dd>{money(sums.paid)}</dd>
      </div>
      <div>
        <dt>Held for sign-off</dt>
        <dd>{money(sums.held)}</dd>
      </div>
    </dl>
  );
}

function payoutCell(claim: ClaimSummary) {
  if (claim.decision === null) return <span className="muted">—</span>;
  if (claim.decision !== "approve") {
    return <DecisionBadge decision={claim.decision} />;
  }
  return <>{money(claim.paid ?? claim.payout ?? 0)}</>;
}

function ariaSort(sort: Sort, key: SortKey) {
  if (sort.key !== key) return undefined;
  return sort.ascending ? "ascending" : "descending";
}

function ClaimTable({
  claims,
  sort,
  onSort,
}: Readonly<{
  claims: ClaimSummary[];
  sort: Sort;
  onSort: (key: SortKey) => void;
}>) {
  return (
    <div className="table-scroll">
      <table className="queue-table">
        <thead>
          <tr>
            {COLUMNS.map((column) => (
              <th
                key={column.key}
                className={column.numeric ? "numeric" : undefined}
                aria-sort={ariaSort(sort, column.key)}
              >
                <button
                  type="button"
                  onClick={() => {
                    onSort(column.key);
                  }}
                >
                  {column.label}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {claims.map((claim) => (
            <tr key={claim.claim_id} className={`row--${claim.status}`}>
              <td>
                <a className="mono" href={`#/claims/${claim.claim_id}`}>
                  {claim.claim_id}
                </a>
              </td>
              <td>
                <ClaimType type={claim.claim_type} />
              </td>
              <td>{claim.customer_name}</td>
              <td>{date(claim.submitted_on)}</td>
              <td className="numeric mono">{money(claim.amount_claimed)}</td>
              <td className="numeric mono">{payoutCell(claim)}</td>
              <td>
                <StatusBadge status={claim.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function QueuePage() {
  const claims = usePoll(api.claims, 3000);
  const agent = usePoll(api.agent, 2000);
  const [filters, setFilters] = useState<Filters>({
    status: "all",
    type: "all",
    search: "",
  });
  const [sort, setSort] = useState<Sort>({ key: "claim_id", ascending: true });
  const all = useMemo(() => claims.data ?? [], [claims.data]);
  const shown = useMemo(
    () => sortClaims(filterClaims(all, filters), sort),
    [all, filters, sort],
  );
  const refresh = () => {
    claims.reload();
    agent.reload();
  };

  return (
    <div className="page">
      <AgentBar
        agent={agent.data}
        waiting={countByStatus(all).waiting}
        onChange={refresh}
      />
      {claims.error && (
        <ErrorNote message={claims.error} onRetry={claims.reload} />
      )}
      {claims.data === null && !claims.error && (
        <Loading label="Loading the queue" />
      )}
      {claims.data !== null && (
        <>
          <StatusTiles
            claims={all}
            selected={filters.status}
            onSelect={(status) => {
              setFilters({ ...filters, status });
            }}
          />
          <MoneyTiles claims={all} />
          <div className="toolbar">
            <label className="field field--grow">
              <span>Search</span>
              <input
                type="search"
                placeholder="Claim, customer or type"
                value={filters.search}
                onChange={(event) => {
                  setFilters({ ...filters, search: event.target.value });
                }}
              />
            </label>
            <label className="field">
              <span>Type</span>
              <select
                value={filters.type}
                onChange={(event) => {
                  setFilters({ ...filters, type: event.target.value });
                }}
              >
                <option value="all">All types</option>
                {claimTypes(all).map((type) => (
                  <option key={type} value={type}>
                    {humanize(type)}
                  </option>
                ))}
              </select>
            </label>
            <p className="toolbar__count" aria-live="polite">
              {shown.length} of {all.length} claims
            </p>
          </div>
          {shown.length === 0 ? (
            <p className="empty">No claims match these filters.</p>
          ) : (
            <ClaimTable
              claims={shown}
              sort={sort}
              onSort={(key) => {
                setSort({
                  key,
                  ascending: sort.key === key ? !sort.ascending : true,
                });
              }}
            />
          )}
        </>
      )}
    </div>
  );
}
