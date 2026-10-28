/** Every page's link, written once. Pages are routed by the URL's hash. */

export type Route =
  | { page: "queue" }
  | { page: "claim"; claimId: string }
  | { page: "instructions" }
  | { page: "insights" }
  | { page: "scoreboard" }
  | { page: "evaluation"; runId: number }
  | { page: "sign-in"; next: string };

const CLAIM = "#/claims/";
const CLAIM_ID = /^[\w-]+$/;
const SCOREBOARD = "#/scoreboard";
const EVALUATION = `${SCOREBOARD}/`;
const RUN_ID = /^\d+$/;
const SIGN_IN = "#/sign-in";
const NEXT = `${SIGN_IN}?next=`;

export const paths = {
  queue: "#/",
  insights: "#/insights",
  instructions: "#/instructions",
  scoreboard: SCOREBOARD,
  claim: (claimId: string) => `${CLAIM}${claimId}`,
  evaluation: (runId: number) => `${EVALUATION}${String(runId)}`,
  /** The sign-in page, which goes on to `next` once a handler signs in. */
  signIn: (next: string) => `${NEXT}${encodeURIComponent(next)}`,
};

function decoded(text: string): string {
  try {
    return decodeURIComponent(text);
  } catch {
    return "";
  }
}

/** Where to go after signing in: the page asked for, or the queue. */
function nextPage(hash: string): string {
  const next = hash.startsWith(NEXT) ? decoded(hash.slice(NEXT.length)) : "";
  return next.startsWith("#/") && !next.startsWith(SIGN_IN)
    ? next
    : paths.queue;
}

export function parseRoute(hash: string): Route {
  if (hash.startsWith(SIGN_IN))
    return { page: "sign-in", next: nextPage(hash) };
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
