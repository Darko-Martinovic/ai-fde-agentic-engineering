import { createContext, useContext, useEffect, useState } from "react";
import { ApiError, api, type Handler } from "./api";
import { onSignInChange } from "./auth";

/** The handler signed in, for every page inside RequireHandler. */
export const HandlerContext = createContext<Handler | null>(null);

export function useHandler(): Handler {
  const handler = useContext(HandlerContext);
  if (!handler) throw new Error("No handler is signed in here");
  return handler;
}

export type SignInState =
  | { status: "checking" }
  | { status: "signed-out" }
  | { status: "signed-in"; handler: Handler }
  | { status: "refused"; message: string };

/** What the backend said of a sign-in, for the user signed in then. */
interface Checked {
  email: string;
  state: SignInState;
}

const NOT_ACCEPTED =
  "Your sign-in wasn't accepted by the backend. Sign out and sign in again.";
// How long a check that failed, as with the backend restarting, waits
const RETRY_MS = 5000;

function refusal(reason: unknown): string | null {
  if (!(reason instanceof ApiError)) return null;
  if (reason.status === 401) return NOT_ACCEPTED;
  return reason.status === 403 ? reason.message : null;
}

/** Who is signed in: the session's user, checked once with the backend, which
 *  finds the handler they are. A token refreshed for the same user changes
 *  nothing. A sign-in the backend turns down says why; a check that fails for
 *  any other reason is tried again. */
export function useSignIn(): SignInState {
  const [email, setEmail] = useState<string | null | undefined>(undefined);
  const [checked, setChecked] = useState<Checked | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => onSignInChange(setEmail), []);
  useEffect(() => {
    if (!email) return;
    const controller = new AbortController();
    let retry: ReturnType<typeof setTimeout> | undefined;
    api.getSignedInHandler(controller.signal).then(
      (handler) => {
        setChecked({ email, state: { status: "signed-in", handler } });
      },
      (reason: unknown) => {
        if (controller.signal.aborted) return;
        const message = refusal(reason);
        if (message) {
          setChecked({ email, state: { status: "refused", message } });
        } else {
          retry = setTimeout(() => {
            setAttempt((n) => n + 1);
          }, RETRY_MS);
        }
      },
    );
    return () => {
      controller.abort();
      clearTimeout(retry);
    };
  }, [email, attempt]);
  if (email === null) return { status: "signed-out" };
  if (email === undefined || checked?.email !== email) {
    return { status: "checking" };
  }
  return checked.state;
}
