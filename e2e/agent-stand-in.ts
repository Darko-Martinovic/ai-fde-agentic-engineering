import { createServer, type IncomingMessage } from "node:http";

// A stand-in for the agent's service in the end-to-end tests, run by Node's own
// TypeScript support. It answers as the service does and keeps what the
// backend asked of it: the claims to pick back up, at GET /api/resumed, and
// the runs to start and stop, at GET /api/started, so the tests never reach the
// service `npm run dev` starts.
const resumed: string[] = [];
const started: unknown[] = [];
const RESUME = /^\/api\/claims\/([^/]+)\/resume$/;
const STARTS: Record<string, string> = {
  "/api/dispatches": "dispatch",
  "/api/evaluations": "evaluation",
  "/api/runs/stop": "stop",
};

async function body(request: IncomingMessage): Promise<object> {
  let text = "";
  for await (const chunk of request) text += String(chunk);
  return text ? (JSON.parse(text) as object) : {};
}

createServer((request, response) => {
  const url = request.url ?? "";
  const claim = RESUME.exec(url);
  response.setHeader("Content-Type", "application/json");
  if (request.method === "POST" && claim) {
    resumed.push(claim[1]);
    response.writeHead(202).end(JSON.stringify({ claim_id: claim[1] }));
  } else if (request.method === "POST" && Object.hasOwn(STARTS, url)) {
    void body(request).then((asked) => {
      started.push({ [STARTS[url]]: asked });
      const reply = STARTS[url] === "stop" ? { stopping: true } : asked;
      response.writeHead(202).end(JSON.stringify(reply));
    });
  } else if (url === "/api/health") {
    response.end(JSON.stringify({ status: "ok" }));
  } else if (url === "/api/resumed") {
    response.end(JSON.stringify(resumed));
  } else if (url === "/api/started") {
    response.end(JSON.stringify(started));
  } else {
    response.writeHead(404).end(JSON.stringify({ detail: "Not found" }));
  }
}).listen(Number(process.env.E2E_AGENT_PORT), process.env.AGENT_HOST);
