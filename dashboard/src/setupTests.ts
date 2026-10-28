import { afterEach, vi } from "vitest";
import { reset } from "./authStandIn";

// No unit test reaches Supabase Auth: auth.ts is the stand-in's, signed in as
// Dana Whitfield until a test signs out or in as someone else.
vi.mock("./auth", () => import("./authStandIn"));

afterEach(() => {
  reset();
});
