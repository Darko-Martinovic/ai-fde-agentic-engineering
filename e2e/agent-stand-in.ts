import {
  createServer,
  type IncomingMessage,
  type ServerResponse,
} from "node:http";

// A stand-in for the agent's service in the end-to-end tests, run by Node's own
// TypeScript support. It answers as the service does and keeps what the
// backend asked of it: the claims to pick back up, at GET /api/resumed, and
// the runs and rounds to start, the runs to stop and the reviews of the
// improver's proposals, at GET /api/started, so the tests never reach the
// service `npm run dev` starts.
const resumed: string[] = [];
const started: unknown[] = [];
const RESUME = /^\/api\/claims\/([^/]+)\/resume$/;
const REVIEW = /^\/api\/rounds\/(\d+)\/proposals\/(\d+)\/review$/;
const STARTS: Record<string, string> = {
  "/api/dispatches": "dispatch",
  "/api/evaluations": "evaluation",
  "/api/runs/stop": "stop",
  "/api/rounds": "round",
};
// What the service answers each start with, beside what it was asked
const REPLIES: Record<string, object> = {
  stop: { stopping: true },
  round: { round_id: 1 },
};

async function body(request: IncomingMessage): Promise<object> {
  let text = "";
  for await (const chunk of request) text += String(chunk);
  return text ? (JSON.parse(text) as object) : {};
}

type Response = ServerResponse;

/** Keep what a POST asked, and answer as the service does; or say it isn't
 *  one the stand-in knows. */
function asked(request: IncomingMessage, response: Response): boolean {
  const url = request.url ?? "";
  const claim = RESUME.exec(url);
  const review = REVIEW.exec(url);
  if (claim) {
    resumed.push(claim[1]);
    response.writeHead(202).end(JSON.stringify({ claim_id: claim[1] }));
  } else if (Object.hasOwn(STARTS, url)) {
    void body(request).then((sent) => {
      started.push({ [STARTS[url]]: sent });
      response.writeHead(202).end(JSON.stringify(REPLIES[STARTS[url]] ?? sent));
    });
  } else if (review) {
    const ids = { round_id: Number(review[1]), proposal_id: Number(review[2]) };
    void body(request).then((sent) => {
      started.push({ review: { ...ids, ...sent } });
      response.writeHead(202).end(JSON.stringify(ids));
    });
  } else {
    return false;
  }
  return true;
}

// What the tests read back
const READS: Record<string, () => unknown> = {
  "/api/health": () => ({ status: "ok" }),
  "/api/resumed": () => resumed,
  "/api/started": () => started,
};

createServer((request, response) => {
  const url = request.url ?? "";
  response.setHeader("Content-Type", "application/json");
  if (request.method === "POST" && asked(request, response)) return;
  if (Object.hasOwn(READS, url)) {
    response.end(JSON.stringify(READS[url]()));
  } else {
    response.writeHead(404).end(JSON.stringify({ detail: "Not found" }));
  }
}).listen(Number(process.env.E2E_AGENT_PORT), process.env.AGENT_HOST);
