import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/** Signing in to the dashboard through Supabase Auth, with an email and a
 *  password: the only module that uses supabase-js. Its session, kept in the
 *  browser, holds the access token the backend checks on a handler's actions. */

let client: SupabaseClient | null = null;

function supabase(): SupabaseClient {
  client ??= createClient(
    import.meta.env.VITE_SUPABASE_URL,
    import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
  );
  return client;
}

/** Sign in, or throw Supabase's refusal. */
export async function signIn(email: string, password: string): Promise<void> {
  const { error } = await supabase().auth.signInWithPassword({
    email,
    password,
  });
  if (error) throw new Error(error.message);
}

export async function signOut(): Promise<void> {
  await supabase().auth.signOut();
}

/** The access token of the session, or null when nobody is signed in. */
export async function accessToken(): Promise<string | null> {
  const { data } = await supabase().auth.getSession();
  return data.session?.access_token ?? null;
}

/** Follow who is signed in: the listener hears the email signed in now, then
 *  each change of user, null once signed out. A token refreshed for the same
 *  user is no change. Returns a way to stop. */
export function onSignInChange(
  listener: (email: string | null) => void,
): () => void {
  let heard: string | null | undefined;
  const { data } = supabase().auth.onAuthStateChange((_event, session) => {
    const email = session?.user.email ?? null;
    if (email !== heard) listener(email);
    heard = email;
  });
  return () => {
    data.subscription.unsubscribe();
  };
}
