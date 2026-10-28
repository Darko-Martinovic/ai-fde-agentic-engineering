import { StateMessage } from "./StateMessage";
import { useEffect, type ReactNode } from "react";
import type { Handler } from "../api";
import { signOut } from "../auth";
import { HandlerContext, useSignIn } from "../handler";
import { paths } from "../paths";

/** Show the page to a signed-in handler only: anyone else goes to the
 *  sign-in page, and comes back to this page once they sign in. */
export function RequireHandler({
  children,
}: Readonly<{ children: (handler: Handler) => ReactNode }>) {
  const signIn = useSignIn();
  useEffect(() => {
    if (signIn.status === "signed-out") {
      window.location.replace(paths.signIn(window.location.hash));
    }
  }, [signIn.status]);
  switch (signIn.status) {
    case "checking":
      return (
        <main className="sign-in">
          <StateMessage kind="loading" message="Checking who's signed in" />
        </main>
      );
    case "signed-out":
      return null;
    case "refused":
      return (
        <main className="sign-in">
          <StateMessage
            kind="error"
            message={signIn.message}
            next="Sign out, then sign in as one of UnderCover's handlers."
            retryLabel="Sign out"
            onRetry={() => {
              void signOut();
            }}
          />
        </main>
      );
    case "signed-in":
      return (
        <HandlerContext.Provider value={signIn.handler}>
          {children(signIn.handler)}
        </HandlerContext.Provider>
      );
  }
}
