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
import { MODELS, calledWith, mockFetch } from "../testing";

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

it("offers 1 to 25 claim agents with 3 chosen, and the models", async () => {
  mockFetch({ "GET /api/models": MODELS });
  render(<DispatchForm running={false} onChange={vi.fn()} />);
  const agents = screen.getByLabelText("Claim agents at once");
  const counts = within(agents).getAllByRole("option");
  expect(counts.map((o) => o.textContent)).toEqual(
    Array.from({ length: 25 }, (_, n) => String(n + 1)),
  );
  expect(agents).toHaveProperty("value", "3");
  await screen.findByRole("option", { name: "GPT-6 Luna (default)" });
  expect(screen.getByLabelText("Model")).toHaveProperty(
    "value",
    "openrouter:openai/gpt-6-luna",
  );
  expect(screen.queryByRole("button", { name: "Stop" })).toBeNull();
});

it("starts a dispatch with the choices made", async () => {
  const onChange = vi.fn();
  const fetchMock = mockFetch({
    "GET /api/models": MODELS,
    "POST /api/dispatches": { agents: 7, model: "anthropic:claude-haiku-5-5" },
  });
  render(<DispatchForm running={false} onChange={onChange} />);
  await screen.findByRole("option", { name: "Claude Haiku 5.5" });
  fireEvent.change(screen.getByLabelText("Claim agents at once"), {
    target: { value: "7" },
  });
  fireEvent.change(screen.getByLabelText("Model"), {
    target: { value: "anthropic:claude-haiku-5-5" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Start a dispatch" }));
  await waitFor(() => {
    expect(onChange).toHaveBeenCalled();
  });
  expect(sentBody(fetchMock, "POST /api/dispatches")).toEqual({
    agents: 7,
    model: "anthropic:claude-haiku-5-5",
  });
});

it.each([
  [409, "A dispatch or an evaluation is already running"],
  [503, "The agent's service isn't running"],
])("shows a refusal (%i) and can start again", async (status, detail) => {
  mockFetch({
    "GET /api/models": MODELS,
    "POST /api/dispatches": Response.json({ detail }, { status }),
  });
  render(<DispatchForm running={false} onChange={vi.fn()} />);
  await screen.findByRole("option", { name: "GPT-6 Luna (default)" });
  const start = screen.getByRole("button", { name: "Start a dispatch" });
  fireEvent.click(start);
  expect((await screen.findByRole("alert")).textContent).toBe(detail);
  expect(start).toHaveProperty("disabled", false);
});

it("stops the dispatch running, and can't start another meanwhile", async () => {
  const fetchMock = mockFetch({
    "GET /api/models": MODELS,
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

it("can't start before the models load", () => {
  mockFetch({});
  render(<DispatchForm running={false} onChange={vi.fn()} />);
  expect(
    screen.getByRole("button", { name: "Start a dispatch" }),
  ).toHaveProperty("disabled", true);
});
