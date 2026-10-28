import { MAX_AGENTS } from "../runs";

const AGENT_COUNTS = Array.from({ length: MAX_AGENTS }, (_, n) => n + 1);

/** How many claim agents a run has at once, from 1 to MAX_AGENTS. */
export function AgentsChoice({
  value,
  onChange,
}: Readonly<{ value: number; onChange: (agents: number) => void }>) {
  return (
    <label className="field">
      <span>Claim agents at once</span>
      <select
        value={value}
        onChange={(event) => {
          onChange(Number(event.target.value));
        }}
      >
        {AGENT_COUNTS.map((agents) => (
          <option key={agents} value={agents}>
            {agents}
          </option>
        ))}
      </select>
    </label>
  );
}
