import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { DispatchForm } from "./DispatchForm";
import { calledWith, mockFetch } from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

function sentBody(fetchMock: ReturnType<typeof mockFetch>, route: string) {
  const [method, path] = route.split(" ");
  const sent = fetchMock.mock.calls.find(
    ([url, init]) => url === path && init?.method === method,
  );
  return JSON.parse(sent?.[1]?.body as string) as unknown;
}

it("offers 1 to 25 claim agents with 3 chosen, and no model to choose", () => {
  mockFetch({});
  render(<DispatchForm running={false} onChange={vi.fn()} />);
  const agents = screen.getByLabelText("Claim agents at once");
  const counts = within(agents).getAllByRole("option");
  expect(counts.map((o) => o.textContent)).toEqual(
    Array.from({ length: 25 }, (_, n) => String(n + 1)),
  );
  expect(agents).toHaveProperty("value", "3");
  expect(screen.queryByLabelText("Model")).toBeNull();
  expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
});

it("starts a dispatch with the claim agents chosen", async () => {
  const onChange = vi.fn();
  const fetchMock = mockFetch({ "POST /api/dispatches": { agents: 7 } });
  render(<DispatchForm running={false} onChange={onChange} />);
  fireEvent.change(screen.getByLabelText("Claim agents at once"), {
    target: { value: "7" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Start a dispatch" }));
  await waitFor(() => {
    expect(onChange).toHaveBeenCalled();
  });
  expect(sentBody(fetchMock, "POST /api/dispatches")).toEqual({ agents: 7 });
});

it.each([
  [409, "A dispatch or an evaluation is already running"],
  [503, "The agent's service isn't running"],
])("shows a refusal (%i) and can start again", async (status, detail) => {
  mockFetch({
    "POST /api/dispatches": Response.json({ detail }, { status }),
  });
  render(<DispatchForm running={false} onChange={vi.fn()} />);
  const start = screen.getByRole("button", { name: "Start a dispatch" });
  fireEvent.click(start);
  expect((await screen.findByRole("alert")).textContent).toBe(detail);
  expect(start).toHaveProperty("disabled", false);
});

it("stops the dispatch running, and can't start another meanwhile", async () => {
  const fetchMock = mockFetch({
    "POST /api/runs/stop-request": { stopping: true },
  });
  render(<DispatchForm running onChange={vi.fn()} />);
  expect(
    screen.getByRole("button", { name: "Start a dispatch" }),
  ).toHaveProperty("disabled", true);
  fireEvent.click(screen.getByRole("button", { name: "Stop" }));
  await waitFor(() => {
    expect(calledWith(fetchMock, "POST /api/runs/stop-request")).toBe(true);
  });
  expect((await screen.findByRole("status")).textContent).toBe(
    "Stopping: no more claims start, and those working finish.",
  );
  expect(screen.getByRole("button", { name: "Stop" })).toHaveProperty(
    "disabled",
    true,
  );
});
