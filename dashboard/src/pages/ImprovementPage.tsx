import { StateMessage } from "../components/StateMessage";
import { useState } from "react";
import { api, type HandlerName, type Improvement, type Round } from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Panel } from "../components/elements";
import { NotAllowed } from "../components/NotAllowed";
import { PageHeader } from "../components/PageHeader";
import { ProposalReview } from "../components/ProposalReview";
import { RoundProgress } from "../components/RoundProgress";
import { RoundsTable } from "../components/RoundsTable";
import { VersionChart } from "../components/VersionChart";
import { when } from "../format";
import { useHandler } from "../handler";
import { who } from "../handlerNames";
import { useAction, usePoll } from "../hooks";
import { paths } from "../paths";

// How often the page reads the rounds again, to follow one as it works
const POLL_MS = 3000;

/** Start a round when none is open, or stop the open one, each after a
 *  confirmation: the page's main action, for a handler who can sign off
 *  over the limit. */
function RoundAction({
  open,
  onDone,
}: Readonly<{ open: Round | undefined; onDone: () => void }>) {
  // The round the handler is asked about, when the dialog opened: none to
  // start one. A poll that finds another closes the dialog.
  const [asked, setAsked] = useState<number | null | undefined>(undefined);
  const { busy, error, run } = useAction(onDone);
  const target = open?.round_id ?? null;
  const confirming = asked !== undefined && asked === target;
  const label = open ? `Stop round ${String(open.round_id)}` : "Start a round";
  return (
    <div className="round-action">
      <button
        type="button"
        className={open ? "button button--danger" : "button button--primary"}
        disabled={busy}
        onClick={() => {
          setAsked(target);
        }}
      >
        {label}
      </button>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <ConfirmDialog
        open={confirming}
        title={`${label}?`}
        confirmLabel={label}
        onCancel={() => {
          setAsked(undefined);
        }}
        onConfirm={() => {
          setAsked(undefined);
          run(() =>
            target === null ? api.startRound() : api.stopRound(target),
          );
        }}
      >
        <p>
          {open
            ? "The round stops before its next step. A version it hasn't judged yet is rolled back."
            : "The current version is evaluated where it needs to be, then the improver follows its recipe and proposes a change for a handler to review. The round spends no more than its spending limit."}
        </p>
      </ConfirmDialog>
    </div>
  );
}

function Recipes({
  improvement,
  handlers,
}: Readonly<{ improvement: Improvement; handlers: HandlerName[] }>) {
  return (
    <Panel title="The improver's recipe">
      <ul className="recipe-list">
        {improvement.recipes.map((recipe) => (
          <li key={recipe.number}>
            <a href={paths.recipe(recipe.number)}>
              Recipe {String(recipe.number)}
            </a>
            {recipe.number === improvement.current_recipe && (
              <span className="badge badge--version-current">Current</span>
            )}
            <span className="cell-note">
              {recipe.approved_by && recipe.approved_at
                ? `${recipe.proposed_by}, approved by ${who(recipe.approved_by, handlers)}, ${when(recipe.approved_at)}`
                : recipe.proposed_by}
            </span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

function openRound(improvement: Improvement): Round | undefined {
  return improvement.rounds.find((round) => round.status === "open");
}

function ImprovementView({
  improvement,
  onChange,
}: Readonly<{ improvement: Improvement; onChange: () => void }>) {
  const handler = useHandler();
  const handlers = usePoll(api.listHandlers, null).data ?? [];
  const open = openRound(improvement);
  return (
    <>
      {!handler.can_approve_over_limit && (
        <NotAllowed action="start or stop a round of improvement" />
      )}
      {open && <RoundProgress round={open} />}
      {open?.waiting && (
        <ProposalReview proposal={open.waiting} onDone={onChange} />
      )}
      {improvement.rounds.length === 0 ? (
        <Panel title="Rounds">
          <StateMessage
            kind="empty"
            message="No rounds yet."
            next="Start a round to have the improver evaluate the current version, propose a change for a handler to review, and keep it only if the held-out claims say it's better."
          />
        </Panel>
      ) : (
        <>
          <VersionChart rounds={improvement.rounds} />
          <RoundsTable rounds={improvement.rounds} handlers={handlers} />
        </>
      )}
      <Recipes improvement={improvement} handlers={handlers} />
    </>
  );
}

/** Improving the claim agent: start or stop a round, follow where it has got
 *  to, review the improver's proposals, and read the rounds so far, the
 *  versions they tried and the recipe's versions. */
export function ImprovementPage() {
  const improvement = usePoll(api.getImprovement, POLL_MS);
  const handler = useHandler();
  const data = improvement.data;
  return (
    <div className="page">
      <PageHeader
        title="Improvement"
        purpose="Rounds in which the improver proposes changes to the claim agent, a handler approves or rejects each, and the held-out claims decide whether a version stays."
        action={
          data &&
          handler.can_approve_over_limit && (
            <RoundAction open={openRound(data)} onDone={improvement.reload} />
          )
        }
      />
      {improvement.error && (
        <StateMessage
          kind="error"
          message={improvement.error}
          onRetry={improvement.reload}
        />
      )}
      {improvement.data === null && !improvement.error && (
        <StateMessage kind="loading" message="Loading the rounds" />
      )}
      {improvement.data && (
        <ImprovementView
          improvement={improvement.data}
          onChange={improvement.reload}
        />
      )}
    </div>
  );
}
