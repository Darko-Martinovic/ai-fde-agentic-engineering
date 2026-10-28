import type { ReactNode } from "react";

// What to do when the dashboard can't load something, unless a caller knows
// better
const TRY_AGAIN =
  "Check that the backend is running, then try again. The page also tries again on its own.";

type State =
  | { kind: "loading"; message: string }
  | { kind: "empty"; message: string; next: ReactNode }
  | {
      kind: "error";
      message: string;
      onRetry: () => void;
      next?: ReactNode;
      /** What the button does, when it's not trying again */
      retryLabel?: string;
    };

/** What a page or a panel shows when it has nothing to show yet: that it's
 *  loading, that there's nothing yet and what to do about it, or that it
 *  couldn't load, why, and what to do next. */
export function StateMessage(props: Readonly<State>) {
  if (props.kind === "loading") {
    return (
      <div className="state state--loading" role="status">
        <span className="spinner" aria-hidden="true" />
        {props.message}
      </div>
    );
  }
  if (props.kind === "empty") {
    return (
      <div className="state state--empty">
        <p>{props.message}</p>
        <p className="state__next">{props.next}</p>
      </div>
    );
  }
  return (
    <div className="state state--error" role="alert">
      <div>
        <p>{props.message}</p>
        <p className="state__next">{props.next ?? TRY_AGAIN}</p>
      </div>
      <button
        type="button"
        className="button button--quiet"
        onClick={props.onRetry}
      >
        {props.retryLabel ?? "Try again"}
      </button>
    </div>
  );
}
