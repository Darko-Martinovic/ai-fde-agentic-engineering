import { api } from "./api";
import { ErrorNote, Loading, Markdown, Panel } from "./components";
import { usePoll } from "./hooks";

function ClaimInstructions() {
  const text = usePoll(api.getInstructions, null);
  return (
    <Panel
      title="The claim agent's instructions"
      className="panel--instructions"
    >
      {text.error && <ErrorNote message={text.error} onRetry={text.reload} />}
      {text.data === null && !text.error && (
        <Loading label="Loading the instructions" />
      )}
      {text.data !== null && <Markdown text={text.data} />}
    </Panel>
  );
}

export function InstructionsPage() {
  const wording = usePoll(api.getPolicyWording, null);

  return (
    <div className="page page--narrow">
      <p className="lede">
        What the UnderCover Agent works from, read only. A dispatch hands each
        claim to a claim agent, which looks up the sections of the policy
        wording and the claims manual it needs.
      </p>
      <ClaimInstructions />
      <Panel>
        <details className="wording">
          <summary>The policy wording</summary>
          {wording.error && (
            <ErrorNote message={wording.error} onRetry={wording.reload} />
          )}
          {wording.data !== null && <Markdown text={wording.data} />}
        </details>
      </Panel>
    </div>
  );
}
