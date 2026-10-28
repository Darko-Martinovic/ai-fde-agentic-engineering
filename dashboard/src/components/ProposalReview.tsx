import { useState } from "react";
import { api, type WaitingProposal } from "../api";
import { useHandler } from "../handler";
import { useAction, useModelLabels } from "../hooks";
import { ConfirmDialog } from "./ConfirmDialog";
import { DiffView } from "./DiffView";
import { Panel } from "./elements";
import { NotAllowed } from "./NotAllowed";

const TITLES = {
  change: "A change waits for your review",
  recipe: "A new recipe waits for your review",
} as const;

/** A change's model and reasoning effort, before it and as proposed. */
function ModelChange({ proposal }: Readonly<{ proposal: WaitingProposal }>) {
  const label = useModelLabels();
  const { model, reasoning_effort: effort } = proposal.proposed;
  const before = proposal.model_before ?? "";
  return (
    <>
      <div>
        <dt>Model before</dt>
        <dd>{`${label(before)} at ${String(proposal.reasoning_effort_before)}`}</dd>
      </div>
      <div>
        <dt>Model proposed</dt>
        <dd>{`${label(model ?? "")} at ${String(effort)}`}</dd>
      </div>
    </>
  );
}

/** A senior handler's two answers: an approval, after a confirmation, or a
 *  rejection with a reason, each sent for the proposal shown. */
function ReviewButtons({
  proposal,
  onDone,
}: Readonly<{ proposal: WaitingProposal; onDone: () => void }>) {
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const { busy, error, run } = useAction(onDone);
  const { round_id: roundId, proposal_id: proposalId } = proposal;
  const what = proposal.kind === "change" ? "change" : "recipe";
  return (
    <form
      className="review-proposal"
      aria-label={`Review the ${what}`}
      onSubmit={(event) => {
        event.preventDefault();
        run(() => api.rejectProposal(roundId, proposalId, note.trim()));
      }}
    >
      <label className="field">
        <span>Why reject it? The improver reads your reason.</span>
        <textarea
          required
          value={note}
          onChange={(event) => {
            setNote(event.target.value);
          }}
        />
      </label>
      <div className="form-actions">
        <button
          type="button"
          className="button button--primary"
          disabled={busy}
          onClick={() => {
            setConfirming(true);
          }}
        >
          Approve the {what}
        </button>
        <button
          type="submit"
          className="button button--quiet"
          disabled={busy || note.trim() === ""}
        >
          Reject the {what}
        </button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <ConfirmDialog
        open={confirming}
        title={`Approve the ${what}?`}
        confirmLabel={`Approve the ${what}`}
        onCancel={() => {
          setConfirming(false);
        }}
        onConfirm={() => {
          setConfirming(false);
          run(() => api.approveProposal(roundId, proposalId));
        }}
      >
        <p>
          {proposal.kind === "change"
            ? "The change becomes a version under test, evaluated once on the evaluation set and twice on the held-out set, then kept or rolled back by the rule."
            : "The recipe becomes the one the improver follows from the next round."}
        </p>
      </ConfirmDialog>
    </form>
  );
}

/** The improver's proposal waiting for a handler: what it would change, the
 *  model and reasoning effort before and after for a change, the improver's
 *  reason, and for a handler who can sign off over the limit, Approve and
 *  Reject. */
export function ProposalReview({
  proposal,
  onDone,
}: Readonly<{ proposal: WaitingProposal; onDone: () => void }>) {
  const handler = useHandler();
  return (
    <Panel title={TITLES[proposal.kind]} className="proposal">
      <dl className="facts">
        {proposal.kind === "change" && <ModelChange proposal={proposal} />}
        <div>
          <dt>The improver&apos;s reason</dt>
          <dd>{proposal.reason}</dd>
        </div>
      </dl>
      <DiffView
        changes={proposal.changes}
        label={`Changes in proposal ${String(proposal.proposal_id)}`}
      />
      {handler.can_approve_over_limit ? (
        <ReviewButtons
          key={proposal.proposal_id}
          proposal={proposal}
          onDone={onDone}
        />
      ) : (
        <NotAllowed action="review the improver's proposals" />
      )}
    </Panel>
  );
}
