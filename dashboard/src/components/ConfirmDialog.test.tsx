import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

afterEach(cleanup);

function dialogWith(open: boolean) {
  const onConfirm = vi.fn();
  const onCancel = vi.fn();
  const view = render(
    <ConfirmDialog
      open={open}
      title="Approve version 2?"
      confirmLabel="Approve"
      onConfirm={onConfirm}
      onCancel={onCancel}
    >
      <p>The claim agent's instructions change.</p>
    </ConfirmDialog>,
  );
  return { onConfirm, onCancel, view };
}

it("is a modal with a title, what changes and two buttons", () => {
  const { onConfirm } = dialogWith(true);
  const dialog = screen.getByRole("dialog", { name: "Approve version 2?" });
  expect(dialog).toHaveProperty("open", true);
  expect(
    screen.getByText("The claim agent's instructions change."),
  ).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Approve" }));
  expect(onConfirm).toHaveBeenCalledOnce();
});

it("closes on Cancel and on Escape without confirming", () => {
  const { onConfirm, onCancel } = dialogWith(true);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent(
    screen.getByRole("dialog"),
    new Event("cancel", { cancelable: true }),
  );
  expect(onCancel).toHaveBeenCalledTimes(2);
  expect(onConfirm).not.toHaveBeenCalled();
});

it("closes when it's no longer open", () => {
  const { view } = dialogWith(true);
  view.rerender(
    <ConfirmDialog
      open={false}
      title="Approve version 2?"
      confirmLabel="Approve"
      onConfirm={vi.fn()}
      onCancel={vi.fn()}
    >
      <p>Gone.</p>
    </ConfirmDialog>,
  );
  expect(screen.queryByRole("dialog")).toBeNull();
});
