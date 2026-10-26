import { createServer } from "node:http";

// A stand-in for the agent's service in the end-to-end tests, run by Node's own
// TypeScript support. It answers as the service does and keeps the claims the
// backend asked it to pick back up, which the tests read at GET /api/resumed,
// so they never reach the service `npm run dev` starts.
const resumed: string[] = [];
const RESUME = /^\/api\/claims\/([^/]+)\/resume$/;

createServer((request, response) => {
  const url = request.url ?? "";
  const claim = RESUME.exec(url);
  response.setHeader("Content-Type", "application/json");
  if (request.method === "POST" && claim) {
    resumed.push(claim[1]);
    response.writeHead(202).end(JSON.stringify({ claim_id: claim[1] }));
  } else if (url === "/api/health") {
    response.end(JSON.stringify({ status: "ok" }));
  } else if (url === "/api/resumed") {
    response.end(JSON.stringify(resumed));
  } else {
    response.writeHead(404).end(JSON.stringify({ detail: "Not found" }));
  }
}).listen(Number(process.env.E2E_AGENT_PORT), process.env.AGENT_HOST);
