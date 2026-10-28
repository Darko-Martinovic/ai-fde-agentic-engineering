import type { RunStatus } from "../api";

const RUN_LABELS: Record<RunStatus, string> = {
  running: "Running",
  finished: "Finished",
  stopped: "Stopped",
};

/** A run's status: Running in Marigold, Finished in Sea Green, Stopped in Coral. */
export function RunBadge({ status }: Readonly<{ status: RunStatus }>) {
  return <span className={`badge badge--${status}`}>{RUN_LABELS[status]}</span>;
}
