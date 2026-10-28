import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { StateMessage } from "./StateMessage";

afterEach(cleanup);

it("says it's loading", () => {
  render(<StateMessage kind="loading" message="Loading the queue" />);
  expect(screen.getByRole("status").textContent).toBe("Loading the queue");
});

it("says there's nothing yet and what to do", () => {
  render(
    <StateMessage
      kind="empty"
      message="No dispatch yet."
      next="Start one above."
    />,
  );
  expect(screen.getByText("No dispatch yet.")).toBeDefined();
  expect(screen.getByText("Start one above.")).toBeDefined();
});

it("says what went wrong, what to do, and tries again", () => {
  const retry = vi.fn();
  render(
    <StateMessage kind="error" message="Failed to fetch" onRetry={retry} />,
  );
  const alert = screen.getByRole("alert");
  expect(alert.textContent).toContain("Failed to fetch");
  expect(alert.textContent).toContain("Check that the backend is running");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledOnce();
});
