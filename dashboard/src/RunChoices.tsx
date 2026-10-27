import type { ModelChoice } from "./api";
import { MAX_AGENTS } from "./runs";

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

/** The model a run works on, from settings/models.toml, MODEL_NAME marked. */
export function ModelChoiceField({
  models,
  value,
  error,
  onChange,
}: Readonly<{
  models: ModelChoice[];
  value: string;
  error: string | null;
  onChange: (spec: string) => void;
}>) {
  return (
    <label className="field">
      <span>Model</span>
      <select
        value={value}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      >
        {models.map((model) => (
          <option key={model.spec} value={model.spec}>
            {model.default ? `${model.label} (default)` : model.label}
          </option>
        ))}
      </select>
      {error && (
        <span className="form-error">Couldn't load the models: {error}</span>
      )}
    </label>
  );
}
