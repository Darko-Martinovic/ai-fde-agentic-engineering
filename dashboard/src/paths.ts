/** Every page's link, written once. Pages are routed by the URL's hash. */

export type Route =
  | { page: "queue" }
  | { page: "claim"; claimId: string }
  | { page: "configuration" }
  | { page: "version"; number: number }
  | { page: "insights" }
  | { page: "scoreboard" }
  | { page: "evaluation"; runId: number }
  | { page: "sign-in"; next: string };

const CLAIM = "#/claims/";
const CLAIM_ID = /^[\w-]+$/;
const SCOREBOARD = "#/scoreboard";
const CONFIGURATION = "#/configuration";
const VERSION = `${CONFIGURATION}/versions/`;
// The Instructions page became the Configuration page; old links still work
const INSTRUCTIONS = "#/instructions";
const EVALUATION = `${SCOREBOARD}/`;
const NUMBER = /^\d+$/;
const INSIGHTS = "#/insights";
const SIGN_IN = "#/sign-in";
const NEXT = `${SIGN_IN}?next=`;

export const paths = {
  queue: "#/",
  insights: INSIGHTS,
  configuration: CONFIGURATION,
  scoreboard: SCOREBOARD,
  claim: (claimId: string) => `${CLAIM}${claimId}`,
  evaluation: (runId: number) => `${EVALUATION}${String(runId)}`,
  version: (number: number) => `${VERSION}${String(number)}`,
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

/** What follows a prefix in the hash, or nothing without the prefix. */
function after(hash: string, prefix: string): string {
  return hash.startsWith(prefix) ? hash.slice(prefix.length) : "";
}

/** A page whose link ends with an id: a claim, an evaluation or a version. */
function pageWithId(hash: string): Route | null {
  const claimId = after(hash, CLAIM);
  if (CLAIM_ID.test(claimId)) return { page: "claim", claimId };
  const runId = after(hash, EVALUATION);
  if (NUMBER.test(runId)) return { page: "evaluation", runId: Number(runId) };
  const number = after(hash, VERSION);
  if (NUMBER.test(number)) return { page: "version", number: Number(number) };
  return null;
}

const PAGES: Partial<Record<string, Route>> = {
  [SCOREBOARD]: { page: "scoreboard" },
  [CONFIGURATION]: { page: "configuration" },
  [INSTRUCTIONS]: { page: "configuration" },
  [INSIGHTS]: { page: "insights" },
};

export function parseRoute(hash: string): Route {
  if (hash.startsWith(SIGN_IN)) {
    return { page: "sign-in", next: nextPage(hash) };
  }
  return pageWithId(hash) ?? PAGES[hash] ?? { page: "queue" };
}
