import type { Step, StepKind } from "./api";
import { Panel } from "./components";
import { clock, pretty } from "./format";

const KIND_LABELS: Record<StepKind, string> = {
  tool_call: "Calls a tool",
  tool_result: "Tool result",
  reply: "Agent",
};

function StepBody({ step }: Readonly<{ step: Step }>) {
  if (step.kind === "tool_call") {
    const space = step.text.indexOf(" ");
    const name = space === -1 ? step.text : step.text.slice(0, space);
    const args = space === -1 ? "" : step.text.slice(space + 1);
    return (
      <p className="step__call">
        <strong className="mono">{name}</strong>{" "}
        <code className="mono">{args}</code>
      </p>
    );
  }
  if (step.kind === "tool_result") {
    const refused = step.text.startsWith("Refused");
    return (
      <details
        className={
          refused ? "step__result step__result--refused" : "step__result"
        }
      >
        <summary>{refused ? step.text : "Show the result"}</summary>
        {!refused && <pre className="mono">{pretty(step.text)}</pre>}
      </details>
    );
  }
  return <p className="step__reply">{step.text}</p>;
}

export function StepsPanel({
  steps,
  live,
}: Readonly<{ steps: Step[] | null; live: boolean }>) {
  return (
    <Panel
      title="What the agent did"
      className="panel--steps"
      actions={
        live ? (
          <span className="live">
            <span className="live__dot" aria-hidden="true" />
            Live
          </span>
        ) : undefined
      }
    >
      {steps?.length ? (
        <ol className="steps" aria-live="polite">
          {steps.map((step, index) => (
            <li
              key={`${step.recorded_at}-${String(index)}`}
              className={`step step--${step.kind}`}
            >
              <span className="step__marker" aria-hidden="true" />
              <div className="step__content">
                <p className="step__meta">
                  <span>{KIND_LABELS[step.kind]}</span>
                  <time dateTime={step.recorded_at}>
                    {clock(step.recorded_at)}
                  </time>
                </p>
                <StepBody step={step} />
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">
          {live
            ? "Waiting for the agent's first step."
            : "The agent hasn't worked on this claim yet."}
        </p>
      )}
    </Panel>
  );
}
