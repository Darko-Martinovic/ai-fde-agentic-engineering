import { createServer } from "node:http";

// A stand-in for the judge in the end-to-end tests, run by Node's own
// TypeScript support: OpenRouter's Decisions endpoint, which grades every
// claim the same, B most likely with a score of 2.2, so no test reaches
// OpenRouter.
const ANSWER = {
  answers: {
    grade: {
      type: "score",
      score: 2.2,
      probabilities: { "0": 0.05, "1": 0.1, "2": 0.45, "3": 0.4 },
    },
    same_grounds: { type: "noul", noul: 0.8 },
    same_section: { type: "noul", noul: 0.3 },
  },
  model: "typesafe/jev-1.13",
  usage: { input_tokens: 400, output_tokens: 3, cost: 0.00002 },
};

createServer((request, response) => {
  response.setHeader("Content-Type", "application/json");
  if (request.method === "POST" && request.url === "/api/alpha/decisions") {
    request.resume();
    request.on("end", () => {
      response.end(JSON.stringify(ANSWER));
    });
  } else if (request.url === "/health") {
    response.end(JSON.stringify({ status: "ok" }));
  } else {
    response.writeHead(404).end(JSON.stringify({ error: "Not found" }));
  }
}).listen(Number(process.env.E2E_JUDGE_PORT), process.env.AGENT_HOST);
