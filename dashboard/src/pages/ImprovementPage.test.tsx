import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ImprovementPage } from "./ImprovementPage";
import type { Round } from "../api";
import {
  HANDLERS,
  SETTINGS_VIEW,
  calledWith,
  changeProposal,
  improvement,
  judgedRound,
  mockFetch,
  recipeProposal,
  renderAs,
  round,
  type Routes,
} from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function routes(rounds: Round[], more: Routes = {}): Routes {
  return {
    "GET /api/improvement": improvement(rounds),
    "GET /api/handlers": HANDLERS,
    "GET /api/settings": SETTINGS_VIEW,
    ...more,
  };
}

function waitingChange(): Round {
  const waiting = changeProposal();
  return round({
    stage: "change_waiting",
    progress: null,
    proposals: [waiting],
    waiting,
  });
}

function posts(fetchMock: ReturnType<typeof mockFetch>, path: string) {
  return fetchMock.mock.calls.filter(
    ([input, init]) => input === path && init?.method === "POST",
  );
}

it("says there are no rounds yet and what starting one does", async () => {
  mockFetch(routes([]));
  renderAs(<ImprovementPage />);
  expect(
    await screen.findByText(/^No rounds yet\. Start a round/),
  ).toBeDefined();
  expect(screen.getByRole("button", { name: "Start a round" })).toBeDefined();
});

it("starts a round once, after a confirmation, and shows a refusal", async () => {
  const fetchMock = mockFetch(
    routes([], {
      "POST /api/improvement/rounds": Response.json(
        { detail: "A dispatch is running" },
        { status: 409 },
      ),
    }),
  );
  renderAs(<ImprovementPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Start a round" }));
  const dialog = screen.getByRole("dialog", { name: "Start a round?" });
  fireEvent.click(
    within(dialog).getByRole("button", { name: "Start a round" }),
  );
  expect((await screen.findByRole("alert")).textContent).toBe(
    "A dispatch is running",
  );
  expect(posts(fetchMock, "/api/improvement/rounds")).toHaveLength(1);
});

it("offers Stop while a round is open, and stops it after a confirmation", async () => {
  const fetchMock = mockFetch(
    routes([round()], { "POST /api/improvement/rounds/1/stop": round() }),
  );
  renderAs(<ImprovementPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Stop round 1" }));
  fireEvent.click(
    within(screen.getByRole("dialog", { name: "Stop round 1?" })).getByRole(
      "button",
      { name: "Stop round 1" },
    ),
  );
  await waitFor(() => {
    expect(calledWith(fetchMock, "POST /api/improvement/rounds/1/stop")).toBe(
      true,
    );
  });
});

it("closes the confirmation, sending nothing, when the round ends meanwhile", async () => {
  const open = routes([round()]);
  const fetchMock = mockFetch(open);
  renderAs(<ImprovementPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Stop round 1" }));
  expect(screen.getByRole("dialog", { name: "Stop round 1?" })).toBeDefined();
  open["GET /api/improvement"] = improvement([judgedRound(1, 2, true, 0.72)]);
  await waitFor(
    () => {
      expect(screen.queryByRole("dialog")).toBeNull();
    },
    { timeout: 5000 },
  );
  expect(screen.getByRole("button", { name: "Start a round" })).toBeDefined();
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(
    false,
  );
}, 10000);

it.each([
  [round(), "First evaluations, 2 of 3"],
  [round({ stage: "improving", progress: null }), "The improver at work"],
  [waitingChange(), "A change waiting for approval"],
  [
    round({ stage: "evaluating", progress: { step: 1, of: 3 } }),
    "Evaluations, 1 of 3",
  ],
  [round({ stage: "verdict", progress: null }), "Verdict"],
  [
    round({ stage: "recipe_waiting", progress: null, version_tried: 2 }),
    "A recipe waiting for approval",
  ],
])("shows where an open round has got to: %#", async (open, said) => {
  mockFetch(routes([open]));
  renderAs(<ImprovementPage />);
  const steps = await screen.findByRole("list", { name: "The round's steps" });
  expect(screen.getByRole("status").textContent).toBe(said);
  expect(within(steps).getByText(said).getAttribute("aria-current")).toBe(
    "step",
  );
  expect(
    screen.getByText("$0.1200 of $0.50", { selector: "dd" }),
  ).toBeDefined();
});

it("passes over the evaluations and verdict of a round that tried no version", async () => {
  mockFetch(
    routes([
      round({
        stage: "recipe_waiting",
        progress: null,
        waiting: recipeProposal(),
      }),
    ]),
  );
  renderAs(<ImprovementPage />);
  const steps = await screen.findByRole("list", { name: "The round's steps" });
  const items = within(steps).getAllByRole("listitem");
  expect(items.map((item) => item.className)).toEqual([
    "round-step round-step--done",
    "round-step round-step--done",
    "round-step round-step--done",
    "round-step round-step--skipped",
    "round-step round-step--skipped",
    "round-step round-step--current",
  ]);
  expect(items[3].textContent).toBe("Evaluations, passed over");
});

it("shows a finished round's verdict and why, and who stopped a stopped one", async () => {
  const stopped = round({
    round_id: 3,
    status: "stopped",
    stage: "stopped",
    progress: null,
    stopped_by: "HND-01",
    stop_reason: "Stopped by Dana Whitfield",
  });
  mockFetch(
    routes([
      stopped,
      judgedRound(2, 3, false, 0.62),
      judgedRound(1, 2, true, 0.72),
    ]),
  );
  renderAs(<ImprovementPage />);
  const table = await screen.findByRole("table", { name: "Rounds" });
  expect(
    within(table).getByText("Kept version 2: accuracy improved"),
  ).toBeDefined();
  expect(
    within(table).getByText(
      "Rolled back version 3: no score improved by more than the noise",
    ),
  ).toBeDefined();
  expect(within(table).getByText("Stopped by Dana Whitfield")).toBeDefined();
});

it("lists each round with its scores, verdict, reviews and cost, right-aligned", async () => {
  mockFetch(routes([judgedRound(1, 2, true, 0.72)]));
  renderAs(<ImprovementPage />);
  const table = await screen.findByRole("table", { name: "Rounds" });
  const row = within(table).getAllByRole("row")[1];
  const accuracy = within(row).getByText("60% → 72%");
  expect(accuracy.className).toBe("numeric");
  expect(within(row).getByText("1.50 → 1.90").className).toBe("numeric");
  expect(within(row).getByText("$0.1200 of $0.50").className).toBe("numeric");
  expect(within(row).getByText("Kept").className).toContain("badge");
  expect(
    await within(row).findByText(
      /^Change approved by Dana Whitfield, Oct 28, 2026/,
    ),
  ).toBeDefined();
  expect(within(row).getByRole("link", { name: "Version 2" })).toBeDefined();
});

it("charts one point per version tried in each chart, by verdict, with version 1's line", async () => {
  mockFetch(
    routes([judgedRound(2, 3, false, 0.62), judgedRound(1, 2, true, 0.72)]),
  );
  renderAs(<ImprovementPage />);
  const accuracy = await screen.findByRole("img", {
    name: "Held-out accuracy of each version tried: version 2 72%, kept; version 3 62%, rolled back; version 1 60%",
  });
  const grade = screen.getByRole("img", {
    name: /^Held-out grade of each version tried: /,
  });
  for (const chart of [accuracy, grade]) {
    const points = chart.querySelectorAll(".version-chart__point");
    expect([...points].map((p) => p.getAttribute("class"))).toEqual([
      "version-chart__point version-chart__point--kept",
      "version-chart__point version-chart__point--rolled-back",
    ]);
    expect(within(chart).getByText("Version tried")).toBeDefined();
  }
  expect(within(accuracy).getByText("Version 1, 60%")).toBeDefined();
  expect(within(accuracy).getByText("Accuracy")).toBeDefined();
  expect(within(grade).getByText("Version 1, 1.50")).toBeDefined();
  expect(within(accuracy).getByText("Version 2: 72%, kept")).toBeDefined();
});

it("says no version has been tried before any verdict", async () => {
  mockFetch(routes([round()]));
  renderAs(<ImprovementPage />);
  expect(
    await screen.findByText(/^No version has been tried yet\./),
  ).toBeDefined();
  expect(screen.getByRole("link", { name: "Recipe 1" })).toBeDefined();
});
