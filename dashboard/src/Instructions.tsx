import { useCallback } from "react";
import { api, type AgentName } from "./api";
import { ErrorNote, Loading, Markdown, Panel } from "./components";
import { usePoll } from "./hooks";

const AGENTS = [
  { agent: "queue", title: "The queue agent's instructions" },
  { agent: "claim", title: "The claim agent's instructions" },
] as const;

function AgentInstructions({
  agent,
  title,
}: Readonly<{ agent: AgentName; title: string }>) {
  const text = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getInstructions(agent, signal),
      [agent],
    ),
    null,
  );
  return (
    <Panel title={title} className="panel--instructions">
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
        What the UnderCover Agent works from, read only. The queue agent hands
        each claim to a claim agent, which looks up the sections of the policy
        wording and the claims manual it needs.
      </p>
      {AGENTS.map(({ agent, title }) => (
        <AgentInstructions key={agent} agent={agent} title={title} />
      ))}
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
