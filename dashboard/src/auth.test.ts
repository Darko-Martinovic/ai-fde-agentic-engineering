import { afterEach, expect, it, vi } from "vitest";

// The real auth.ts, on a stand-in for supabase-js's client
vi.unmock("./auth");

const supabaseAuth = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(),
}));
const createClient = vi.hoisted(() => vi.fn(() => ({ auth: supabaseAuth })));
vi.mock("@supabase/supabase-js", () => ({ createClient }));

const { accessToken, onSignInChange, signIn, signOut } = await import("./auth");

afterEach(() => {
  vi.clearAllMocks();
});

it("signs in with an email and a password", async () => {
  supabaseAuth.signInWithPassword.mockResolvedValue({ error: null });
  await signIn("dana.whitfield@undercover.example", "secret");
  expect(supabaseAuth.signInWithPassword).toHaveBeenCalledWith({
    email: "dana.whitfield@undercover.example",
    password: "secret",
  });
});

it("passes on Supabase's refusal", async () => {
  supabaseAuth.signInWithPassword.mockResolvedValue({
    error: { message: "Invalid login credentials" },
  });
  await expect(signIn("dana@example.com", "wrong")).rejects.toThrow(
    "Invalid login credentials",
  );
});

it("gives the session's access token, or none", async () => {
  supabaseAuth.getSession.mockResolvedValue({
    data: { session: { access_token: "token" } },
  });
  expect(await accessToken()).toBe("token");
  supabaseAuth.getSession.mockResolvedValue({ data: { session: null } });
  expect(await accessToken()).toBeNull();
});

it("follows who is signed in until told to stop", () => {
  const unsubscribe = vi.fn();
  const dana = { user: { email: "dana@example.com" } };
  supabaseAuth.onAuthStateChange.mockImplementation(
    (callback: (event: string, session: object | null) => void) => {
      callback("INITIAL_SESSION", dana);
      callback("TOKEN_REFRESHED", dana);
      callback("SIGNED_OUT", null);
      callback("SIGNED_IN", { user: { email: "marcus@example.com" } });
      return { data: { subscription: { unsubscribe } } };
    },
  );
  const heard: (string | null)[] = [];
  const stop = onSignInChange((email) => heard.push(email));
  expect(heard).toEqual(["dana@example.com", null, "marcus@example.com"]);
  stop();
  expect(unsubscribe).toHaveBeenCalled();
});

it("signs out", async () => {
  supabaseAuth.signOut.mockResolvedValue({ error: null });
  await signOut();
  expect(supabaseAuth.signOut).toHaveBeenCalled();
});
