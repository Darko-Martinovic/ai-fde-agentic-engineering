import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

afterEach(cleanup);

/** The dialog as a page uses it: open until confirmed or cancelled. */
function Confirming({ onConfirm }: Readonly<{ onConfirm: () => void }>) {
  const [open, setOpen] = useState(true);
  return (
    <ConfirmDialog
      open={open}
      title="Approve version 2?"
      confirmLabel="Approve"
      onConfirm={() => {
        setOpen(false);
        onConfirm();
      }}
      onCancel={() => {
        setOpen(false);
      }}
    >
      <p>The claim agent&apos;s instructions change.</p>
    </ConfirmDialog>
  );
}

it("is a modal with a title, what changes and two buttons", () => {
  const onConfirm = vi.fn();
  render(<Confirming onConfirm={onConfirm} />);
  const dialog = screen.getByRole("dialog", { name: "Approve version 2?" });
  expect(dialog).toHaveProperty("open", true);
  expect(
    screen.getByText("The claim agent's instructions change."),
  ).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  expect(onConfirm).toHaveBeenCalledOnce();
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("closes on Cancel without confirming", () => {
  const onConfirm = vi.fn();
  render(<Confirming onConfirm={onConfirm} />);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(onConfirm).not.toHaveBeenCalled();
});

it("closes on Escape, through the page's state, without confirming", () => {
  const onConfirm = vi.fn();
  render(<Confirming onConfirm={onConfirm} />);
  const escape = new Event("cancel", { cancelable: true });
  fireEvent(screen.getByRole("dialog"), escape);
  expect(escape.defaultPrevented).toBe(true);
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(onConfirm).not.toHaveBeenCalled();
});
