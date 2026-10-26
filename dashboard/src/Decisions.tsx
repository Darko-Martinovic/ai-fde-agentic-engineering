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
import { HandlerPicker } from "./HandlerPicker";
import { useHandlerChoice, who } from "./handlers";
import { useAction } from "./hooks";
import { ReviewForm } from "./ReviewForm";

/** A handler's review of the decision's payout: who signed it off, or who
 *  rejected it and why. */
function ReviewLine({
  decision,
  handlers,
}: Readonly<{ decision: Decision; handlers: Handler[] }>) {
  if (!decision.review || !decision.reviewed_by || !decision.reviewed_at) {
    return null;
  }
  const by = `${who(decision.reviewed_by, handlers)} at ${clock(decision.reviewed_at)}`;
  return decision.review === "signed_off" ? (
    <p className="decision__review">Signed off by {by}.</p>
  ) : (
    <p className="decision__review decision__review--rejected">
      Rejected by {by}: {decision.review_note}
    </p>
  );
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
      <ReviewLine decision={decision} handlers={handlers} />
    </article>
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

/** The payment, with its sign-off if it had one, or that the agent is about to
 *  pay an approval. */
function PaymentNote({
  claim,
  handlers,
}: Readonly<{ claim: Claim; handlers: Handler[] }>) {
  const { payment } = claim;
  const latest = claim.decisions.at(-1);
  if (payment?.signed_off_at) {
    return (
      <p className="note note--success">
        Paid {money(payment.amount)}, signed off by{" "}
        {who(payment.authorized_by, handlers)} at {clock(payment.signed_off_at)}
      </p>
    );
  }
  if (payment) {
    return (
      <p className="note note--success">
        Paid {money(payment.amount)} on {date(payment.paid_at)}, authorized by{" "}
        {who(payment.authorized_by, handlers)}
      </p>
    );
  }
  if (claim.status !== "in_progress" || latest?.decision !== "approve") {
    return null;
  }
  return latest.review === "rejected" ? (
    <p className="note">Waiting for the agent to look at the claim again.</p>
  ) : (
    <p className="note">Waiting for the agent to pay it.</p>
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
      <PaymentNote claim={claim} handlers={handlers} />
      {claim.status === "awaiting_sign_off" && (
        <ReviewForm claim={claim} handlers={handlers} onDone={onChange} />
      )}
      {FOR_A_HANDLER.includes(claim.status) && (
        <ReferralForm claim={claim} handlers={handlers} onDone={onChange} />
      )}
    </Panel>
  );
}
