/** Every page's link, written once. Pages are routed by the URL's hash. */

export type Route =
  | { page: "queue" }
  | { page: "claim"; claimId: string }
  | { page: "instructions" }
  | { page: "insights" }
  | { page: "scoreboard" }
  | { page: "evaluation"; runId: number };

const CLAIM = "#/claims/";
const CLAIM_ID = /^[\w-]+$/;
const SCOREBOARD = "#/scoreboard";
const EVALUATION = `${SCOREBOARD}/`;
const RUN_ID = /^\d+$/;

export const paths = {
  queue: "#/",
  insights: "#/insights",
  instructions: "#/instructions",
  scoreboard: SCOREBOARD,
  claim: (claimId: string) => `${CLAIM}${claimId}`,
  evaluation: (runId: number) => `${EVALUATION}${String(runId)}`,
};

export function parseRoute(hash: string): Route {
  const claimId = hash.startsWith(CLAIM) ? hash.slice(CLAIM.length) : "";
  if (CLAIM_ID.test(claimId)) return { page: "claim", claimId };
  const runId = hash.startsWith(EVALUATION)
    ? hash.slice(EVALUATION.length)
    : "";
  if (RUN_ID.test(runId)) return { page: "evaluation", runId: Number(runId) };
  if (hash === paths.scoreboard) return { page: "scoreboard" };
  if (hash === paths.instructions) return { page: "instructions" };
  if (hash === paths.insights) return { page: "insights" };
  return { page: "queue" };
}
