import { useHandler } from "../handler";

/** Why the signed-in handler sees no button for an action only a handler who
 *  can sign off payouts over the limit may take. The backend refuses it too. */
export function NotAllowed({ action }: Readonly<{ action: string }>) {
  const handler = useHandler();
  return (
    <p className="note note--locked" role="note">
      Only a handler who can sign off payouts over the approval limit can{" "}
      {action}. You&apos;re signed in as {handler.name}, who can&apos;t.
    </p>
  );
}
