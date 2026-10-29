import { setting } from "../settings/settings.config.ts";

// The agent's key, which every request the tests make as the agent carries,
// as the agent's own requests do.
export const AS_THE_AGENT = { "X-API-Key": setting("E2E_API_KEY") };
