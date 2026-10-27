import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ScoreboardPage } from "./Scoreboard";
import { MODELS, evaluation, mockFetch } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

it("lists the evaluations newest first with their measures", async () => {
  mockFetch({
    "GET /api/evaluations": [
      evaluation({ run_id: 5 }),
      evaluation({ evaluation_set: "evaluation", tiny: false }),
    ],
    "GET /api/models": MODELS,
  });
  render(<ScoreboardPage />);
  const table = await screen.findByRole("table", { name: "Evaluations" });
  const rows = within(table).getAllByRole("row").slice(1);
  expect(
    rows.map((r) => within(r).getAllByRole("cell")[0]?.textContent),
  ).toEqual(["#5", "#4"]);
  const first = within(rows[0]);
  expect(first.getByRole("link", { name: "#5" }).getAttribute("href")).toBe(
    "#/scoreboard/5",
  );
  expect(first.getByText("Held-out set, 3 tiny")).toBeDefined();
  for (const value of ["80%", "40%", "$1,600.00", "60%", "$0.0125", "40 s"]) {
    expect(first.getByText(value)).toBeDefined();
  }
  expect(first.getByText("2 min 41 s")).toBeDefined();
  expect(first.getByText("Finished")).toBeDefined();
  expect(within(rows[1]).getByText("Evaluation set, all 3")).toBeDefined();
  expect(await first.findByText("GPT-6 Luna, low reasoning")).toBeDefined();
});

it("says when there is no evaluation yet", async () => {
  mockFetch({ "GET /api/evaluations": [], "GET /api/models": MODELS });
  render(<ScoreboardPage />);
  expect(await screen.findByText("No evaluation yet.")).toBeDefined();
});

it("starts with the evaluation set, all 25 and 3 agents, and posts the choices", async () => {
  const fetchMock = mockFetch({
    "GET /api/evaluations": [],
    "GET /api/models": MODELS,
    "POST /api/evaluations": {
      agents: 5,
      model: "openrouter:openai/gpt-6-luna",
    },
  });
  render(<ScoreboardPage />);
  const form = screen.getByRole("form", { name: "Start an evaluation" });
  expect(within(form).getByLabelText("Set")).toHaveProperty(
    "value",
    "evaluation",
  );
  expect(within(form).getByLabelText("Claims")).toHaveProperty("value", "all");
  expect(within(form).getByLabelText("Claim agents at once")).toHaveProperty(
    "value",
    "3",
  );
  await screen.findByRole("option", { name: "GPT-6 Luna (default)" });
  fireEvent.change(within(form).getByLabelText("Set"), {
    target: { value: "held_out" },
  });
  fireEvent.change(within(form).getByLabelText("Claims"), {
    target: { value: "tiny" },
  });
  fireEvent.change(within(form).getByLabelText("Claim agents at once"), {
    target: { value: "5" },
  });
  fireEvent.click(
    within(form).getByRole("button", { name: "Start an evaluation" }),
  );
  await waitFor(() => {
    const sent = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "POST",
    );
    expect(JSON.parse(sent?.[1]?.body as string)).toEqual({
      evaluation_set: "held_out",
      tiny: true,
      agents: 5,
      model: "openrouter:openai/gpt-6-luna",
    });
  });
});

it.each([
  [409, "A dispatch or an evaluation is already running"],
  [503, "The agent's service isn't running"],
])("shows a refusal (%i)", async (status, detail) => {
  mockFetch({
    "GET /api/evaluations": [],
    "GET /api/models": MODELS,
    "POST /api/evaluations": Response.json({ detail }, { status }),
  });
  render(<ScoreboardPage />);
  await screen.findByRole("option", { name: "GPT-6 Luna (default)" });
  fireEvent.click(screen.getByRole("button", { name: "Start an evaluation" }));
  expect((await screen.findByRole("alert")).textContent).toBe(detail);
});

it("shows when the evaluations can't load", async () => {
  mockFetch({ "GET /api/models": MODELS });
  render(<ScoreboardPage />);
  expect(
    await screen.findByText("No route for GET /api/evaluations"),
  ).toBeDefined();
});
