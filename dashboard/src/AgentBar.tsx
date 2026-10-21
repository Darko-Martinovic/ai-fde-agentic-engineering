import { api, type AgentState } from "./api";
import { useAction } from "./hooks";

function describe(agent: AgentState | null): string {
  if (agent === null) return "Checking the agent";
  if (!agent.running) return "The agent is idle";
  const where = agent.claim_id ? `on ${agent.claim_id}` : "starting up";
  return agent.mode === "queue"
    ? `Working through the queue, ${where}`
    : `Working ${where}`;
}

export function AgentBar({
  agent,
  waiting,
  onChange,
}: Readonly<{
  agent: AgentState | null;
  waiting: number;
  onChange: () => void;
}>) {
  const { busy, error, run: act } = useAction(onChange);
  const running = agent?.running ?? false;

  return (
    <section
      className={`agent-bar${running ? " agent-bar--running" : ""}`}
      aria-label="UnderCover Agent"
    >
      <span className="agent-bar__pulse" aria-hidden="true" />
      <div className="agent-bar__text">
        <strong>UnderCover Agent</strong>
        <span>{describe(agent)}</span>
        {agent && (
          <span className="agent-bar__model">Model: {agent.model}</span>
        )}
        {error && <span className="agent-bar__error">{error}</span>}
      </div>
      <div className="agent-bar__actions">
        <button
          type="button"
          className="button button--primary"
          disabled={busy || running || waiting === 0}
          onClick={() => {
            act(api.runQueue);
          }}
        >
          Run queue
        </button>
        <button
          type="button"
          className="button button--danger"
          disabled={busy || !running}
          onClick={() => {
            act(api.stopAgent);
          }}
        >
          Stop
        </button>
      </div>
    </section>
  );
}
