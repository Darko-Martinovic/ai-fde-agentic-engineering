import type { HandlerName, Round } from "../api";
import { when } from "../format";
import { who } from "../handlerNames";
import {
  accuracyLine,
  endLine,
  gradeLine,
  reviewLine,
  spentLine,
  stageLabel,
  verdictLine,
} from "../improvement";
import { paths } from "../paths";
import { Panel } from "./elements";

const ROUND_STATUS = {
  open: "Open",
  finished: "Finished",
  stopped: "Stopped",
} as const;

/** The verdict on the version a round tried, as a chip and why, or where an
 *  open round has got to, or how a round with no verdict ended. */
function Outcome({ round }: Readonly<{ round: Round }>) {
  if (round.verdict) {
    return (
      <>
        <span className={`badge badge--version-${round.verdict}`}>
          {round.verdict === "kept" ? "Kept" : "Rolled back"}
        </span>
        <span className="cell-note">{verdictLine(round)}</span>
        {round.status === "stopped" && (
          <span className="cell-note">{endLine(round)}</span>
        )}
      </>
    );
  }
  return (
    <>
      <span className={`badge badge--round-${round.status}`}>
        {ROUND_STATUS[round.status]}
      </span>
      <span className="cell-note">{endLine(round) ?? stageLabel(round)}</span>
    </>
  );
}

function RoundRow({
  round,
  handlers,
}: Readonly<{ round: Round; handlers: HandlerName[] }>) {
  return (
    <tr>
      <th scope="row">Round {String(round.round_id)}</th>
      <td>
        {who(round.started_by, handlers)}
        <span className="cell-note">{when(round.started_at)}</span>
      </td>
      <td className="numeric">{String(round.recipe_number)}</td>
      <td>
        {round.version_tried === null ? (
          "None"
        ) : (
          <a href={paths.version(round.version_tried)}>
            Version {String(round.version_tried)}
          </a>
        )}
      </td>
      <td className="numeric">
        {accuracyLine(round.scores_before)} → {accuracyLine(round.scores_after)}
      </td>
      <td className="numeric">
        {gradeLine(round.scores_before)} → {gradeLine(round.scores_after)}
      </td>
      <td>
        <Outcome round={round} />
      </td>
      <td>
        <ul className="cell-list">
          {round.proposals.map((proposal) => (
            <li key={proposal.proposal_id}>{reviewLine(proposal, handlers)}</li>
          ))}
        </ul>
      </td>
      <td className="numeric">{spentLine(round)}</td>
    </tr>
  );
}

/** Every round, newest first: who started it, the recipe it followed, the
 *  version it tried with its held-out scores before and after, the verdict
 *  and why, who reviewed what and when, and what it cost against its limit. */
export function RoundsTable({
  rounds,
  handlers,
}: Readonly<{ rounds: Round[]; handlers: HandlerName[] }>) {
  return (
    <Panel title="Rounds">
      <div className="table-scroll">
        <table className="data-table rounds-table" aria-label="Rounds">
          <thead>
            <tr>
              <th scope="col">Round</th>
              <th scope="col">Started by</th>
              <th scope="col" className="numeric">
                Recipe
              </th>
              <th scope="col">Version tried</th>
              <th scope="col" className="numeric">
                Held-out accuracy
              </th>
              <th scope="col" className="numeric">
                Held-out grade
              </th>
              <th scope="col">Verdict</th>
              <th scope="col">Reviews</th>
              <th scope="col" className="numeric">
                Spent of the limit
              </th>
            </tr>
          </thead>
          <tbody>
            {rounds.map((round) => (
              <RoundRow
                key={round.round_id}
                round={round}
                handlers={handlers}
              />
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
