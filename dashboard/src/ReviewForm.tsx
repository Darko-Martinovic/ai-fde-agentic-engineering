import { useState, type SyntheticEvent } from "react";
import { api, type Claim, type Handler } from "./api";
import { money } from "./format";
import { HandlerPicker } from "./HandlerPicker";
import { useHandlerChoice } from "./handlers";
import { useAction } from "./hooks";

/** A handler's review of a held payout: sign it off, and the agent pays it, or
 *  reject it with a note, which goes back to the agent. */
export function ReviewForm({
  claim,
  handlers,
  onDone,
}: Readonly<{ claim: Claim; handlers: Handler[]; onDone: () => void }>) {
  const [handlerId, setHandlerId] = useHandlerChoice(handlers);
  const [note, setNote] = useState("");
  const { busy, error, run } = useAction(onDone);
  const payout = claim.decisions.at(-1)?.payout ?? 0;
  const send = (approved: boolean) => {
    run(() =>
      api.reviewPayout(claim.claim_id, {
        handler_id: handlerId,
        approved,
        note: note.trim(),
      }),
    );
  };
  const signOff = (event: SyntheticEvent) => {
    event.preventDefault();
    send(true);
  };
  return (
    <form className="action-form action-form--sign-off" onSubmit={signOff}>
      <h3>Review the payout</h3>
      <p>
        The agent approved {money(payout)}, which waits for a handler. Sign it
        off and the agent pays it, or reject it with a note that says what's
        wrong, and the agent looks at the claim again.
      </p>
      <HandlerPicker
        handlers={handlers}
        value={handlerId}
        onChange={setHandlerId}
      />
      <label className="field">
        <span>Note for the agent</span>
        <textarea
          rows={2}
          value={note}
          onChange={(event) => {
            setNote(event.target.value);
          }}
        />
      </label>
      {error && <p className="form-error">{error}</p>}
      <div className="action-form__buttons">
        <button
          type="submit"
          className="button button--primary"
          disabled={busy || !handlerId}
        >
          Sign off {money(payout)}
        </button>
        <button
          type="button"
          className="button button--secondary"
          disabled={busy || !handlerId || note.trim() === ""}
          onClick={() => {
            send(false);
          }}
        >
          Reject
        </button>
      </div>
    </form>
  );
}
