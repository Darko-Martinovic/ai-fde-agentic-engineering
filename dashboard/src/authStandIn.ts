/** A stand-in for auth.ts in the unit tests, which setupTests.ts puts in its
 *  place: a session in memory, signed in as Dana Whitfield to start with, so
 *  no test reaches Supabase Auth. Its access token is `<email>-token`. */

const DANA = "dana.whitfield@undercover.example";
let email: string | null = DANA;
let token: string | null = `${DANA}-token`;
let refusal: string | null = null;
const listeners = new Set<(email: string | null) => void>();

function tell() {
  for (const listener of listeners) listener(email);
}

/** Sign in as this email, or sign out with null. */
export function signInAs(next: string | null) {
  email = next;
  token = next && `${next}-token`;
  tell();
}

/** Refresh the access token for the same handler, as supabase-js does. */
export function refreshToken() {
  token = `${String(email)}-refreshed`;
}

/** Turn the next sign-ins down with Supabase's message. */
export function refuseSignIns(message: string) {
  refusal = message;
}

export function reset() {
  email = DANA;
  token = `${DANA}-token`;
  refusal = null;
  listeners.clear();
}

export function signIn(address: string, password: string): Promise<void> {
  if (refusal || !password) {
    return Promise.reject(new Error(refusal ?? "No password"));
  }
  signInAs(address);
  return Promise.resolve();
}

export function signOut(): Promise<void> {
  signInAs(null);
  return Promise.resolve();
}

export function accessToken(): Promise<string | null> {
  return Promise.resolve(token);
}

export function onSignInChange(
  listener: (email: string | null) => void,
): () => void {
  listeners.add(listener);
  listener(email);
  return () => {
    listeners.delete(listener);
  };
}
