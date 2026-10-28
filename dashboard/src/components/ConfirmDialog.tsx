import { useEffect, useId, useRef, type ReactNode } from "react";

/** The dashboard's own confirmation, before anything that changes the agent
 *  or a setting: a modal `<dialog>` with a title, what will change, and two
 *  buttons. Escape or Cancel closes it without doing anything. */
export function ConfirmDialog({
  open,
  title,
  confirmLabel,
  children,
  onConfirm,
  onCancel,
}: Readonly<{
  open: boolean;
  title: string;
  confirmLabel: string;
  children: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
}>) {
  const dialog = useRef<HTMLDialogElement>(null);
  const heading = useId();
  useEffect(() => {
    const shown = dialog.current;
    if (!shown) return;
    if (open && !shown.open) shown.showModal();
    if (!open && shown.open) shown.close();
  }, [open]);
  return (
    <dialog
      ref={dialog}
      className="confirm"
      aria-labelledby={heading}
      onCancel={(event) => {
        event.preventDefault();
        onCancel();
      }}
    >
      <h2 id={heading}>{title}</h2>
      <div className="confirm__body">{children}</div>
      <div className="confirm__buttons">
        <button
          type="button"
          className="button button--quiet"
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="button"
          className="button button--primary"
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
