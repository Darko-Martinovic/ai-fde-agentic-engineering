/** Every page's link, written once. Pages are routed by the URL's hash. */

export type Route =
  | { page: "queue" }
  | { page: "claim"; claimId: string }
  | { page: "instructions" }
  | { page: "insights" };

const CLAIM = "#/claims/";
const CLAIM_ID = /^[\w-]+$/;

export const paths = {
  queue: "#/",
  insights: "#/insights",
  instructions: "#/instructions",
  claim: (claimId: string) => `${CLAIM}${claimId}`,
};

export function parseRoute(hash: string): Route {
  const claimId = hash.startsWith(CLAIM) ? hash.slice(CLAIM.length) : "";
  if (CLAIM_ID.test(claimId)) return { page: "claim", claimId };
  if (hash === paths.instructions) return { page: "instructions" };
  if (hash === paths.insights) return { page: "insights" };
  return { page: "queue" };
}
