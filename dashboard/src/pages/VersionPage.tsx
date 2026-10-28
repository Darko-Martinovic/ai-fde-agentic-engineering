import { useCallback } from "react";
import { api, type VersionDetails } from "../api";
import { approval } from "../configuration";
import { DiffView } from "../components/DiffView";
import { ErrorNote, Loading, Markdown, Panel } from "../components/elements";
import { PageHeader } from "../components/PageHeader";
import { VersionBadge } from "../components/VersionBadge";
import { clock, date } from "../format";
import { useModelLabels, usePoll } from "../hooks";
import { paths } from "../paths";

/** The model and reasoning effort before a version and in it. */
function ModelChange({ version }: Readonly<{ version: VersionDetails }>) {
  const label = useModelLabels();
  const before = version.based_on_model
    ? `${label(version.based_on_model)} at ${String(version.based_on_reasoning_effort)}`
    : "None";
  return (
    <>
      <div>
        <dt>Model before</dt>
        <dd>{before}</dd>
      </div>
      <div>
        <dt>Model in this version</dt>
        <dd>{`${label(version.model)} at ${version.reasoning_effort}`}</dd>
      </div>
    </>
  );
}

function VersionFacts({ version }: Readonly<{ version: VersionDetails }>) {
  const handlers = usePoll(api.listHandlers, null);
  return (
    <Panel title="What changed and why">
      <dl className="facts">
        <ModelChange version={version} />
        <div>
          <dt>Based on</dt>
          <dd>
            {version.based_on === null ? (
              "Nothing: the first version"
            ) : (
              <a href={paths.version(version.based_on)}>
                Version {String(version.based_on)}
              </a>
            )}
          </dd>
        </div>
        <div>
          <dt>Reason</dt>
          <dd>{version.reason}</dd>
        </div>
        <div>
          <dt>Proposed by</dt>
          <dd>
            {version.proposed_by}, {date(version.created_at)} at{" "}
            {clock(version.created_at)}
          </dd>
        </div>
        <div>
          <dt>Approved</dt>
          <dd>{approval(version, handlers.data ?? [])}</dd>
        </div>
        <div>
          <dt>Verdict</dt>
          <dd>{version.verdict_reason ?? "Not decided yet"}</dd>
        </div>
      </dl>
    </Panel>
  );
}

function VersionView({ version }: Readonly<{ version: VersionDetails }>) {
  return (
    <>
      <VersionFacts version={version} />
      <Panel title="Changes to the instructions">
        <DiffView
          changes={version.changes}
          label={`Changes in version ${String(version.number)}`}
        />
      </Panel>
      <Panel>
        <details className="instructions">
          <summary>The instructions in full</summary>
          <Markdown text={version.instructions} />
        </details>
      </Panel>
    </>
  );
}

/** One version of the claim agent's configuration: what it changed from the
 *  version it was based on, who proposed and approved it, and its verdict. */
export function VersionPage({ number }: Readonly<{ number: number }>) {
  const version = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getVersionDetails(number, signal),
      [number],
    ),
    5000,
  );
  return (
    <div className="page">
      <a className="back" href={paths.configuration}>
        Back to the configuration
      </a>
      <PageHeader
        title={`Version ${String(number)}`}
        purpose="One version of the claim agent's instructions, model and reasoning effort, beside the version it was based on."
        action={version.data && <VersionBadge status={version.data.status} />}
      />
      {version.error && (
        <ErrorNote message={version.error} onRetry={version.reload} />
      )}
      {version.data === null && !version.error && (
        <Loading label={`Loading version ${String(number)}`} />
      )}
      {version.data && <VersionView version={version.data} />}
    </div>
  );
}
