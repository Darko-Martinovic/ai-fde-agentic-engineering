import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { AgentBar } from "./AgentBar";
import { IDLE, MODELS, mockFetch } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

function bar(waiting: number) {
  render(<AgentBar agent={IDLE} waiting={waiting} onChange={vi.fn()} />);
}

function button(name: string) {
  return screen.getByRole("button", { name });
}

it("says which model the running agent works on", () => {
  mockFetch({ "GET /api/agent/models": MODELS });
  render(
    <AgentBar
      agent={{
        model: "Claude Haiku 5.5",
        running: true,
        mode: "queue",
        claim_id: "CLM-1001",
      }}
      waiting={3}
      onChange={vi.fn()}
    />,
  );
  expect(
    screen.getByText(
      "Working through the queue, on CLM-1001, with Claude Haiku 5.5",
    ),
  ).toBeDefined();
});

it("runs no more claims than are waiting, and none for an empty cap", async () => {
  mockFetch({ "GET /api/agent/models": MODELS });
  bar(3);
  await screen.findByRole("option", { name: "Claude Haiku 5.5" });
  expect(button("Run 3")).toHaveProperty("disabled", false);
  const claims = screen.getByLabelText("Claims");
  fireEvent.change(claims, { target: { value: "" } });
  expect(button("Run")).toHaveProperty("disabled", true);
  fireEvent.change(claims, { target: { value: "2.5" } });
  expect(button("Run 2")).toHaveProperty("disabled", false);
  expect(button("Run all 3")).toHaveProperty("disabled", false);
});

it("leaves the counts off when nothing is waiting", async () => {
  mockFetch({ "GET /api/agent/models": MODELS });
  bar(0);
  await screen.findByRole("option", { name: "Claude Haiku 5.5" });
  expect(button("Run")).toHaveProperty("disabled", true);
  expect(button("Run all")).toHaveProperty("disabled", true);
});

it("keeps the model picked for the next page", async () => {
  mockFetch({ "GET /api/agent/models": MODELS });
  bar(3);
  await screen.findByRole("option", { name: "Claude Haiku 5.5" });
  fireEvent.change(screen.getByLabelText("Model"), {
    target: { value: "anthropic:claude-haiku-5-5" },
  });
  cleanup();
  bar(3);
  await screen.findByRole("option", { name: "Claude Haiku 5.5" });
  expect(screen.getByLabelText("Model")).toHaveProperty(
    "value",
    "anthropic:claude-haiku-5-5",
  );
});

it("says when the models can't be loaded", async () => {
  mockFetch({});
  bar(3);
  expect(
    await screen.findByText(
      "Couldn't load the models: No route for GET /api/agent/models",
    ),
  ).toBeDefined();
  expect(button("Run 3")).toHaveProperty("disabled", true);
});
