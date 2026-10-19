import type { Claim, Customer, Policy } from "./api";
import { Panel } from "./components";
import { date, humanize, money } from "./format";

export function StoryPanel({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <Panel title="The customer's story">
      <blockquote className="story">{claim.story}</blockquote>
      <p className="muted">
        Incident on {date(claim.incident_date)} in {claim.incident_location}
      </p>
    </Panel>
  );
}

export function ItemsPanel({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <Panel title="Items claimed">
      <table className="items">
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th className="numeric">Amount</th>
          </tr>
        </thead>
        <tbody>
          {claim.items.map((item, index) => (
            <tr key={`${item.description}-${String(index)}`}>
              <td>{item.description}</td>
              <td>
                <span className="chip">{humanize(item.category)}</span>
              </td>
              <td className="numeric mono">{money(item.amount)}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th colSpan={2}>Total claimed</th>
            <td className="numeric mono">{money(claim.amount_claimed)}</td>
          </tr>
        </tfoot>
      </table>
    </Panel>
  );
}

export function DocumentsPanel({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <Panel title={`Documents (${String(claim.documents.length)})`}>
      <ul className="documents">
        {claim.documents.map((document) => (
          <li key={document.name}>
            <details>
              <summary>
                <span>{document.name}</span>
                <span className="chip">{humanize(document.type)}</span>
              </summary>
              <p>{document.content}</p>
            </details>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

const LIMITS: { key: keyof Policy["plan"]; label: string }[] = [
  { key: "trip_cancellation_max", label: "Trip cancellation" },
  { key: "trip_delay_max", label: "Trip delay" },
  { key: "baggage_delay_max", label: "Baggage delay" },
  { key: "baggage_max", label: "Baggage" },
  { key: "per_item_limit", label: "Per item" },
  { key: "passport_max", label: "Passport" },
  { key: "emergency_medical_max", label: "Emergency medical" },
  { key: "deductible", label: "Deductible" },
];

export function PolicyPanel({ policy }: Readonly<{ policy: Policy | null }>) {
  if (policy === null) return <Panel title="Policy">Loading the policy</Panel>;
  const { plan, trip } = policy;
  return (
    <Panel
      title="Policy"
      actions={<span className="chip chip--plan">{plan.name}</span>}
    >
      <dl className="facts">
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Trip</dt>
        <dd>
          {trip.destination}, {date(trip.departs_on)} to {date(trip.returns_on)}
        </dd>
        <dt>Trip cost</dt>
        <dd className="mono">{money(trip.trip_cost)}</dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
        <dt>Bought</dt>
        <dd>
          {date(policy.purchased_on)} through {policy.sold_through}
        </dd>
        <dt>Waiting periods</dt>
        <dd>
          Trip delay {plan.trip_delay_waiting_hours} hours, baggage delay{" "}
          {plan.baggage_delay_waiting_hours} hours
        </dd>
      </dl>
      <ul className="limits">
        {LIMITS.map(({ key, label }) => (
          <li key={key}>
            <span>{label}</span>
            <strong className="mono">{money(Number(plan[key]))}</strong>
          </li>
        ))}
      </ul>
      {policy.add_ons.length > 0 && (
        <ul className="add-ons">
          {policy.add_ons.map((addOn) => (
            <li key={addOn.add_on}>
              <strong>{addOn.name}</strong> {addOn.effect}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export function CustomerPanel({
  customer,
}: Readonly<{ customer: Customer | null }>) {
  if (customer === null) {
    return <Panel title="Customer">Loading the customer</Panel>;
  }
  return (
    <Panel title="Customer">
      <p className="customer__name">{customer.name}</p>
      <p className="muted">
        Customer since {date(customer.customer_since)} · {customer.email}
      </p>
      <h3 className="subhead">
        Earlier claims ({String(customer.previous_claims.length)})
      </h3>
      {customer.previous_claims.length === 0 ? (
        <p className="muted">None.</p>
      ) : (
        <ul className="history">
          {customer.previous_claims.map((previous) => (
            <li key={previous.claim_id}>
              <span className="mono">{previous.claim_id}</span>
              <span>{previous.summary}</span>
              <span className="muted">
                {date(previous.filed_on)} · {humanize(previous.outcome)} ·{" "}
                {money(previous.amount_paid)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
