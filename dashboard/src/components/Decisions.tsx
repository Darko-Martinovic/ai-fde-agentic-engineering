import { useState, type SyntheticEvent } from "react";
import {
  FOR_A_HANDLER,
  api,
  type Claim,
  type Decision,
  type HandlerName,
} from "../api";
import { DecisionBadge, Panel } from "./elements";
import { clock, date, money } from "../format";
import { useHandler } from "../handler";
import { who } from "../handlerNames";
import { useAction, useSettings } from "../hooks";
import { NotAllowed } from "./NotAllowed";
import { ReviewForm } from "./ReviewForm";

/** A handler's review of the decision's payout: who signed it off, or who
 *  rejected it and why. */
function ReviewLine({
  decision,
  handlers,
}: Readonly<{ decision: Decision; handlers: HandlerName[] }>) {
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
}: Readonly<{ decision: Decision; handlers: HandlerName[] }>) {
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

function SubmitDecision({
  label,
  disabled,
}: Readonly<{ label: string; disabled: boolean }>) {
  return (
    <button
      type="submit"
      className="button button--primary"
      disabled={disabled}
    >
      {label}
    </button>
  );
}

/** Whether an approval is over the approval limit as the settings stand. */
function useOverLimit(decision: HandlerDecision, amount: number): boolean {
  const limit = useSettings()?.settings.approval_limit;
  return decision === "approve" && limit !== undefined && amount > limit;
}

function ReferralForm({
  claim,
  onDone,
}: Readonly<{ claim: Claim; onDone: () => void }>) {
  const [decision, setDecision] = useState<HandlerDecision>("approve");
  const [payout, setPayout] = useState("");
  const [reasons, setReasons] = useState("");
  const { busy, error, run } = useAction(onDone);
  const handler = useHandler();
  const amount = Number(payout);
  const valid = reasons.trim() !== "" && (decision === "decline" || amount > 0);
  const overLimit = useOverLimit(decision, amount);

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    run(() =>
      api.decideAsHandler(claim.claim_id, {
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
      {overLimit && !handler.can_approve_over_limit ? (
        <NotAllowed action="approve a payout over the limit" />
      ) : (
        <SubmitDecision
          label={submitLabel(decision, amount)}
          disabled={busy || !valid}
        />
      )}
    </form>
  );
}

/** The payment, with its sign-off if it had one, or that the agent is about to
 *  pay an approval. */
function PaymentNote({
  claim,
  handlers,
}: Readonly<{ claim: Claim; handlers: HandlerName[] }>) {
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

/** What a handler can do on a claim: sign off or reject a held payout, or
 *  decide a claim referred or left for them. */
function HandlerForms({
  claim,
  onChange,
}: Readonly<{ claim: Claim; onChange: () => void }>) {
  return (
    <>
      {claim.status === "awaiting_sign_off" && (
        <ReviewForm claim={claim} onDone={onChange} />
      )}
      {FOR_A_HANDLER.includes(claim.status) && (
        <ReferralForm claim={claim} onDone={onChange} />
      )}
    </>
  );
}

/** An evaluation's copy is scored on the agent's work alone: nobody reviews
 *  or decides it. */
function CopyNote({ claim }: Readonly<{ claim: Claim }>) {
  if (claim.status === "awaiting_sign_off") {
    return (
      <p className="note">
        Held for sign-off. In an evaluation this counts as finished, and a copy
        can&apos;t be signed off.
      </p>
    );
  }
  if (FOR_A_HANDLER.includes(claim.status)) {
    return (
      <p className="note">
        Left for a handler. In an evaluation this counts as the agent&apos;s
        answer, and a handler doesn&apos;t decide a copy.
      </p>
    );
  }
  return null;
}

export function DecisionPanel({
  claim,
  handlers,
  onChange,
}: Readonly<{ claim: Claim; handlers: HandlerName[]; onChange: () => void }>) {
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
      {claim.evaluation_id === null ? (
        <HandlerForms claim={claim} onChange={onChange} />
      ) : (
        <CopyNote claim={claim} />
      )}
    </Panel>
  );
}
