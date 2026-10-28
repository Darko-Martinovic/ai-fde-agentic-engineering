import {
  generateKeyPairSync,
  randomUUID,
  sign,
  type KeyObject,
} from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";

// A stand-in for Supabase Auth in the end-to-end tests, run by Node's own
// TypeScript support. It signs in the handlers in data/handlers.json with
// E2E_HANDLER_PASSWORD, signs their access tokens with an EC P-256 key made
// as it starts, publishes the public key where Supabase does, and answers the
// browser's cross-origin checks, so no test reaches Supabase.
const KEY_ID = "e2e-key";
const { privateKey, publicKey } = generateKeyPairSync("ec", {
  namedCurve: "P-256",
});
const handlers = JSON.parse(
  readFileSync(new URL("../data/handlers.json", import.meta.url), "utf-8"),
) as { email: string }[];
const emails = new Set(handlers.map((handler) => handler.email));
const HOUR = 3600;

function encoded(part: object): string {
  return Buffer.from(JSON.stringify(part)).toString("base64url");
}

function accessToken(email: string, key: KeyObject): string {
  const now = Math.floor(Date.now() / 1000);
  const header = encoded({ alg: "ES256", typ: "JWT", kid: KEY_ID });
  const claims = encoded({
    sub: email,
    email,
    aud: "authenticated",
    role: "authenticated",
    iat: now,
    exp: now + HOUR,
  });
  const signature = sign("sha256", Buffer.from(`${header}.${claims}`), {
    key,
    dsaEncoding: "ieee-p1363",
  }).toString("base64url");
  return `${header}.${claims}.${signature}`;
}

function user(email: string) {
  return {
    id: email,
    aud: "authenticated",
    role: "authenticated",
    email,
    app_metadata: { provider: "email" },
    user_metadata: {},
    created_at: new Date(0).toISOString(),
  };
}

function session(email: string) {
  return {
    access_token: accessToken(email, privateKey),
    token_type: "bearer",
    expires_in: HOUR,
    expires_at: Math.floor(Date.now() / 1000) + HOUR,
    refresh_token: randomUUID(),
    user: user(email),
  };
}

function emailOf(request: IncomingMessage): string | null {
  const token = request.headers.authorization?.replace("Bearer ", "") ?? "";
  try {
    const claims = token.split(".")[1] ?? "";
    const parsed = JSON.parse(Buffer.from(claims, "base64url").toString()) as {
      email?: string;
    };
    return parsed.email ?? null;
  } catch {
    return null;
  }
}

async function body(request: IncomingMessage): Promise<Record<string, string>> {
  let text = "";
  for await (const chunk of request) text += String(chunk);
  return text ? (JSON.parse(text) as Record<string, string>) : {};
}

const KEYS = {
  keys: [
    {
      ...publicKey.export({ format: "jwk" }),
      kid: KEY_ID,
      alg: "ES256",
      use: "sig",
    },
  ],
};

type Reply = (status: number, data: object | null) => void;

// Each refresh token handed out, and whose session it renews
const refreshTokens = new Map<string, string>();

function signedIn(email: string) {
  const started = session(email);
  refreshTokens.set(started.refresh_token, email);
  return started;
}

function refresh(token: string, reply: Reply) {
  const email = refreshTokens.get(token);
  if (email) reply(200, signedIn(email));
  else reply(400, { code: 400, msg: "Invalid Refresh Token" });
}

/** The password grant, or a refresh of a session it started. */
function grantToken(request: IncomingMessage, reply: Reply) {
  const grant = new URLSearchParams((request.url ?? "").split("?")[1]).get(
    "grant_type",
  );
  void body(request).then(({ email = "", password = "", refresh_token }) => {
    if (grant === "refresh_token") {
      refresh(refresh_token, reply);
    } else if (
      emails.has(email) &&
      password === process.env.E2E_HANDLER_PASSWORD
    ) {
      reply(200, signedIn(email));
    } else {
      reply(400, {
        code: 400,
        error_code: "invalid_credentials",
        msg: "Invalid login credentials",
      });
    }
  });
}

const ROUTES: Partial<
  Record<string, (request: IncomingMessage, reply: Reply) => void>
> = {
  "POST /auth/v1/token": grantToken,
  "GET /auth/v1/.well-known/jwks.json": (_request, reply) => {
    reply(200, KEYS);
  },
  "GET /auth/v1/user": (request, reply) => {
    const email = emailOf(request);
    reply(email ? 200 : 401, email ? user(email) : { msg: "No session" });
  },
  "POST /auth/v1/logout": (_request, reply) => {
    reply(204, null);
  },
  "GET /health": (_request, reply) => {
    reply(200, { status: "ok" });
  },
};

createServer((request, response) => {
  const path = (request.url ?? "/").split("?")[0];
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("Access-Control-Allow-Headers", "*");
  response.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  response.setHeader("Content-Type", "application/json");
  const reply: Reply = (status, data) => {
    response.writeHead(status).end(data === null ? "" : JSON.stringify(data));
  };
  const route = ROUTES[`${request.method ?? "GET"} ${path}`];
  if (request.method === "OPTIONS") reply(204, null);
  else if (route) route(request, reply);
  else reply(404, { msg: "Not found" });
}).listen(Number(process.env.E2E_AUTH_PORT), process.env.AGENT_HOST);
