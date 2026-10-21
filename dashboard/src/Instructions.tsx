import { api } from "./api";
import { ErrorNote, Loading, Markdown, Panel } from "./components";
import { usePoll } from "./hooks";

export function InstructionsPage() {
  const instructions = usePoll(api.getInstructions, null);
  const wording = usePoll(api.getPolicyWording, null);

  return (
    <div className="page page--narrow">
      <p className="lede">
        What the UnderCover Agent works from. These are read only: the agent
        follows them, and the policy wording sits in its prompt.
      </p>
      <Panel title="The agent's instructions" className="panel--instructions">
        {instructions.error && (
          <ErrorNote
            message={instructions.error}
            onRetry={instructions.reload}
          />
        )}
        {instructions.data === null && !instructions.error && (
          <Loading label="Loading the instructions" />
        )}
        {instructions.data !== null && <Markdown text={instructions.data} />}
      </Panel>
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
