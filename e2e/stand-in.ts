import type { APIRequestContext } from "@playwright/test";
import { setting } from "../settings/settings.config.ts";

// What the backend asked of the stand-in for the agent's service, which
// playwright.config.ts starts: the one way the tests reach it.
const AGENT = setting("E2E_AGENT_URL");

async function read<T>(request: APIRequestContext, path: string): Promise<T> {
  return (await (await request.get(`${AGENT}${path}`)).json()) as T;
}

/** The claims the backend asked the agent's service to pick back up. */
export function resumed(request: APIRequestContext): Promise<string[]> {
  return read(request, "/api/resumed");
}

/** The runs the backend asked it to start and stop, as each was asked. */
export function started(request: APIRequestContext): Promise<object[]> {
  return read(request, "/api/started");
}
