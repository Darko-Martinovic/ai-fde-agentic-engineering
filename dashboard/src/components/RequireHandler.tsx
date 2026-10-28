import { useEffect, type ReactNode } from "react";
import type { Handler } from "../api";
import { signOut } from "../auth";
import { HandlerContext, useSignIn } from "../handler";
import { paths } from "../paths";
import { Loading } from "./elements";

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
          <Loading label="Checking who's signed in" />
        </main>
      );
    case "signed-out":
      return null;
    case "refused":
      return (
        <main className="sign-in">
          <div className="note note--error" role="alert">
            <span>{signIn.message}</span>
            <button
              type="button"
              className="button button--quiet"
              onClick={() => {
                void signOut();
              }}
            >
              Sign out
            </button>
          </div>
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
