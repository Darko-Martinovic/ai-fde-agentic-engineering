import type { Round, Stage } from "../api";
import { STAGE_LABELS, STEPS, spentLine, stageLabel } from "../improvement";
import { Panel } from "./elements";

type StepState = "done" | "current" | "next" | "skipped";

// The steps a round with no version tried passes over
const FOR_A_VERSION: Stage[] = ["evaluating", "verdict"];

function stateOf(round: Round, index: number, current: number): StepState {
  if (index === current) return "current";
  if (index > current) return "next";
  const passedOver =
    round.version_tried === null && FOR_A_VERSION.includes(STEPS[index]);
  return passedOver ? "skipped" : "done";
}

/** Where an open round has got to: its steps in order, the current one marked
 *  with how far it has got, such as "First evaluations, 2 of 3", and what it
 *  has spent of its limit. */
export function RoundProgress({ round }: Readonly<{ round: Round }>) {
  const current = STEPS.indexOf(round.stage);
  return (
    <Panel title={`Round ${String(round.round_id)}`}>
      <p className="round-now" role="status">
        <span className="live__dot" aria-hidden="true" />
        {stageLabel(round)}
      </p>
      <ol className="round-steps" aria-label="The round's steps">
        {STEPS.map((stage, index) => {
          const state = stateOf(round, index, current);
          return (
            <li
              key={stage}
              className={`round-step round-step--${state}`}
              aria-current={state === "current" ? "step" : undefined}
            >
              {state === "current" ? stageLabel(round) : STAGE_LABELS[stage]}
              {state === "skipped" && (
                <span className="visually-hidden">, passed over</span>
              )}
            </li>
          );
        })}
      </ol>
      <dl className="facts facts--row">
        <div>
          <dt>Spent</dt>
          <dd className="numeric">{spentLine(round)}</dd>
        </div>
        <div>
          <dt>Started from</dt>
          <dd>
            Version {String(round.version_before)}, recipe{" "}
            {String(round.recipe_number)}
          </dd>
        </div>
      </dl>
    </Panel>
  );
}
