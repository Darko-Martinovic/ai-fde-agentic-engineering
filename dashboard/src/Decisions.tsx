import { useState, type SyntheticEvent } from "react";
import {
  FOR_A_HANDLER,
  api,
  type Claim,
  type Decision,
  type Handler,
} from "./api";
import { DecisionBadge, Panel } from "./components";
import { clock, date, money } from "./format";
import { useAction } from "./hooks";

function who(id: string, handlers: Handler[]): string {
  if (id === "agent") return "UnderCover Agent";
  return handlers.find((h) => h.handler_id === id)?.name ?? id;
}

function DecisionCard({
  decision,
  handlers,
}: Readonly<{ decision: Decision; handlers: Handler[] }>) {
  return (
    <article className={`decision decision--${decision.decision}`}>
      <header>
        <DecisionBadge decision={decision.decision} />
        {decision.decision === "approve" && (
          <strong className="decision__payout mono">
            {money(decision.payout)}
          </strong>
        )}
      </header>
      <p>{decision.reasons}</p>
      {decision.policy_section && (
        <p className="decision__section">{decision.policy_section}</p>
      )}
      <p className="muted">
        {who(decision.decided_by, handlers)}, {date(decision.decided_at)} at{" "}
        {clock(decision.decided_at)}
      </p>
    </article>
  );
}

function HandlerPicker({
  handlers,
  value,
  onChange,
}: Readonly<{
  handlers: Handler[];
  value: string;
  onChange: (id: string) => void;
}>) {
  return (
    <label className="field">
      <span>Handler</span>
      <select
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        {handlers.map((handler) => (
          <option key={handler.handler_id} value={handler.handler_id}>
            {handler.name}, {handler.role}
          </option>
        ))}
      </select>
    </label>
  );
}

/** The handler picked in a form: the first handler until someone picks one,
 *  including when the handlers arrive after the form. */
function useHandlerChoice(handlers: Handler[]) {
  const [picked, setPicked] = useState("");
  return [picked || (handlers[0]?.handler_id ?? ""), setPicked] as const;
}

function SignOffForm({
  claim,
  handlers,
  onDone,
}: Readonly<{ claim: Claim; handlers: Handler[]; onDone: () => void }>) {
  const [handlerId, setHandlerId] = useHandlerChoice(handlers);
  const { busy, error, run } = useAction(onDone);
  const payout = claim.decisions.at(-1)?.payout ?? 0;
  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    run(() => api.signOffClaim(claim.claim_id, handlerId));
  };
  return (
    <form className="action-form action-form--sign-off" onSubmit={submit}>
      <h3>Sign off the payment</h3>
      <p>
        The agent approved {money(payout)}. A payout over $1,000.00 is paid once
        a handler signs it off.
      </p>
      <HandlerPicker
        handlers={handlers}
        value={handlerId}
        onChange={setHandlerId}
      />
      {error && <p className="form-error">{error}</p>}
      <button
        type="submit"
        className="button button--primary"
        disabled={busy || !handlerId}
      >
        Sign off {money(payout)}
      </button>
    </form>
  );
}

type HandlerDecision = "approve" | "decline";

function DecisionChoice({
  value,
  onChange,
}: Readonly<{
  value: HandlerDecision;
  onChange: (decision: HandlerDecision) => void;
}>) {
  return (
    <fieldset className="choice">
      <legend>Decision</legend>
      {(["approve", "decline"] as const).map((option) => (
        <label key={option}>
          <input
            type="radio"
            name="decision"
            value={option}
            checked={value === option}
            onChange={() => {
              onChange(option);
            }}
          />
          {option === "approve" ? "Approve" : "Decline"}
        </label>
      ))}
    </fieldset>
  );
}

function submitLabel(decision: HandlerDecision, amount: number): string {
  return decision === "approve" && amount > 0
    ? `Approve and pay ${money(amount)}`
    : "Record the decision";
}

function ReferralForm({
  claim,
  handlers,
  onDone,
}: Readonly<{ claim: Claim; handlers: Handler[]; onDone: () => void }>) {
  const [handlerId, setHandlerId] = useHandlerChoice(handlers);
  const [decision, setDecision] = useState<HandlerDecision>("approve");
  const [payout, setPayout] = useState("");
  const [reasons, setReasons] = useState("");
  const { busy, error, run } = useAction(onDone);
  const amount = Number(payout);
  const valid =
    handlerId !== "" &&
    reasons.trim() !== "" &&
    (decision === "decline" || amount > 0);

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    run(() =>
      api.decideAsHandler(claim.claim_id, {
        handler_id: handlerId,
        decision,
        payout: decision === "approve" ? amount : 0,
        reasons: reasons.trim(),
      }),
    );
  };

  return (
    <form className="action-form action-form--referral" onSubmit={submit}>
      <h3>
        {claim.status === "referred"
          ? "Decide the referral"
          : "Decide the claim"}
      </h3>
      <HandlerPicker
        handlers={handlers}
        value={handlerId}
        onChange={setHandlerId}
      />
      <DecisionChoice value={decision} onChange={setDecision} />
      {decision === "approve" && (
        <label className="field">
          <span>Payout in US dollars</span>
          <input
            type="number"
            min="0.01"
            step="0.01"
            inputMode="decimal"
            value={payout}
            onChange={(event) => {
              setPayout(event.target.value);
            }}
          />
        </label>
      )}
      <label className="field">
        <span>Reasons</span>
        <textarea
          rows={3}
          value={reasons}
          onChange={(event) => {
            setReasons(event.target.value);
          }}
        />
      </label>
      {error && <p className="form-error">{error}</p>}
      <button
        type="submit"
        className="button button--primary"
        disabled={busy || !valid}
      >
        {submitLabel(decision, amount)}
      </button>
    </form>
  );
}

export function DecisionPanel({
  claim,
  handlers,
  onChange,
}: Readonly<{ claim: Claim; handlers: Handler[]; onChange: () => void }>) {
  return (
    <Panel title="Decision" className="panel--decision">
      {claim.decisions.length === 0 && (
        <p className="muted">No decision yet.</p>
      )}
      {claim.decisions.map((decision) => (
        <DecisionCard
          key={decision.decided_at}
          decision={decision}
          handlers={handlers}
        />
      ))}
      {claim.payment && (
        <p className="note note--success">
          Paid {money(claim.payment.amount)} on {date(claim.payment.paid_at)},
          authorized by {who(claim.payment.authorized_by, handlers)}
        </p>
      )}
      {claim.status === "awaiting_sign_off" && (
        <SignOffForm claim={claim} handlers={handlers} onDone={onChange} />
      )}
      {FOR_A_HANDLER.includes(claim.status) && (
        <ReferralForm claim={claim} handlers={handlers} onDone={onChange} />
      )}
    </Panel>
  );
}
