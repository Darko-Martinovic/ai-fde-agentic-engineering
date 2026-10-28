import { useCallback } from "react";
import {
  api,
  type Configuration,
  type HandlerName,
  type Version,
} from "../api";
import { ErrorNote, Loading, Markdown, Panel } from "../components/elements";
import { PageHeader } from "../components/PageHeader";
import { VersionBadge } from "../components/VersionBadge";
import { modelLabel, approval } from "../configuration";
import { usePoll } from "../hooks";
import { paths } from "../paths";

function CurrentVersion({
  configuration,
}: Readonly<{ configuration: Configuration }>) {
  const number = configuration.current;
  const version = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getVersionDetails(number, signal),
      [number],
    ),
    null,
  );
  const current = configuration.versions.find((v) => v.number === number);
  return (
    <Panel title={`Current version: ${String(number)}`}>
      {current && (
        <dl className="facts facts--row">
          <div>
            <dt>Model</dt>
            <dd>{modelLabel(configuration.models_allowed, current.model)}</dd>
          </div>
          <div>
            <dt>Reasoning effort</dt>
            <dd>{current.reasoning_effort}</dd>
          </div>
          <div>
            <dt>Proposed by</dt>
            <dd>{current.proposed_by}</dd>
          </div>
        </dl>
      )}
      {version.error && (
        <ErrorNote message={version.error} onRetry={version.reload} />
      )}
      {version.data && (
        <details className="instructions">
          <summary>The claim agent&apos;s instructions</summary>
          <Markdown text={version.data.instructions} />
        </details>
      )}
    </Panel>
  );
}

function VersionRow({
  version,
  configuration,
  handlers,
}: Readonly<{
  version: Version;
  configuration: Configuration;
  handlers: HandlerName[];
}>) {
  return (
    <tr>
      <td>
        <a href={paths.version(version.number)}>
          Version {String(version.number)}
        </a>
      </td>
      <td>
        <VersionBadge status={version.status} />
      </td>
      <td>{modelLabel(configuration.models_allowed, version.model)}</td>
      <td>{version.reasoning_effort}</td>
      <td className="numeric">
        <span className="added">+{String(version.lines_added)}</span>{" "}
        <span className="removed">−{String(version.lines_removed)}</span>
      </td>
      <td>{version.proposed_by}</td>
      <td>{approval(version, handlers)}</td>
      <td>{version.verdict_reason ?? ""}</td>
    </tr>
  );
}

function VersionsTable({
  configuration,
}: Readonly<{ configuration: Configuration }>) {
  const handlers = usePoll(api.listHandlers, null);
  return (
    <Panel title="Versions">
      <div className="table-scroll">
        <table className="data-table" aria-label="Versions">
          <thead>
            <tr>
              <th scope="col">Version</th>
              <th scope="col">Status</th>
              <th scope="col">Model</th>
              <th scope="col">Reasoning effort</th>
              <th scope="col" className="numeric">
                Lines changed
              </th>
              <th scope="col">Proposed by</th>
              <th scope="col">Approved</th>
              <th scope="col">Why kept or rolled back</th>
            </tr>
          </thead>
          <tbody>
            {configuration.versions.map((version) => (
              <VersionRow
                key={version.number}
                version={version}
                configuration={configuration}
                handlers={handlers.data ?? []}
              />
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function PolicyWording() {
  const wording = usePoll(api.getPolicyWording, null);
  return (
    <Panel>
      <details className="wording">
        <summary>The policy wording the claim agent works from</summary>
        {wording.error && (
          <ErrorNote message={wording.error} onRetry={wording.reload} />
        )}
        {wording.data !== null && <Markdown text={wording.data} />}
      </details>
    </Panel>
  );
}

/** The claim agent's configuration: the current version and every version,
 *  with what each changed and why. Read only: changes come from the
 *  improver, approved by a handler. */
export function ConfigurationPage() {
  const configuration = usePoll(api.getConfiguration, 5000);
  return (
    <div className="page">
      <PageHeader
        title="Configuration"
        purpose="The claim agent's instructions, model and reasoning effort, kept in versions. Dispatches and evaluations use the current version."
      />
      {configuration.error && (
        <ErrorNote
          message={configuration.error}
          onRetry={configuration.reload}
        />
      )}
      {configuration.data === null && !configuration.error && (
        <Loading label="Loading the configuration" />
      )}
      {configuration.data && (
        <>
          <CurrentVersion configuration={configuration.data} />
          <VersionsTable configuration={configuration.data} />
        </>
      )}
      <PolicyWording />
    </div>
  );
}
