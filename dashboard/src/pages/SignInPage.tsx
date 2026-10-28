import { useState, type SyntheticEvent } from "react";
import { signIn } from "../auth";
import { Logo } from "../components/elements";
import { errorMessage } from "../hooks";

/** Sign in with an email and a password; there's no sign-up. A handler who
 *  signs in goes on to the page they asked for. */
export function SignInPage({ next }: Readonly<{ next: string }>) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    setBusy(true);
    setError(null);
    signIn(email.trim(), password).then(
      () => {
        window.location.hash = next;
      },
      (reason: unknown) => {
        setError(errorMessage(reason));
        setBusy(false);
      },
    );
  };
  return (
    <main className="sign-in">
      <form className="sign-in__panel" onSubmit={submit}>
        <div className="brand">
          <Logo />
          <span>
            <strong>UnderCover</strong>
            <em>Claims desk</em>
          </span>
        </div>
        <h1>Sign in</h1>
        <p className="muted">
          For UnderCover&apos;s claims handlers. Ask your team lead if you
          don&apos;t have an account.
        </p>
        <label className="field">
          <span>Email</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
          />
        </label>
        <label className="field">
          <span>Password</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
          />
        </label>
        {error && (
          <p className="note note--error" role="alert">
            {error}
          </p>
        )}
        <button
          type="submit"
          className="button button--primary"
          disabled={busy}
        >
          {busy ? "Signing in" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
