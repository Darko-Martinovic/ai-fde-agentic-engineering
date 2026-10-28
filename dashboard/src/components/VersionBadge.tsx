import type { VersionStatus } from "../api";

const VERSION_LABELS: Record<VersionStatus, string> = {
  current: "Current",
  kept: "Kept",
  under_test: "Under test",
  rolled_back: "Rolled back",
};

/** Where a version stands: Current in Sea Green, Kept in Cerulean, Under test
 *  in Marigold, Rolled back in Coral. */
export function VersionBadge({ status }: Readonly<{ status: VersionStatus }>) {
  return (
    <span className={`badge badge--version-${status}`}>
      {VERSION_LABELS[status]}
    </span>
  );
}
