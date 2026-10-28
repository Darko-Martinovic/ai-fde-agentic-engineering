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
  MARCUS,
  SETTINGS_VIEW,
  changeProposal,
  improvement,
  mockFetch,
  recipeProposal,
  renderAs,
  round,
  type Routes,
} from "../testing";

// The proposal waiting for a handler on the Improvement page: its diff, and
// Approve and Reject

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const PROPOSAL = "/api/improvement/rounds/1/proposals/1";
// Another round and proposal, so ids swapped would show
const OTHER = "/api/improvement/rounds/2/proposals/5";

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

it("shows a waiting change's diff, its model before and after, and its reason", async () => {
  mockFetch(routes([waitingChange()]));
  renderAs(<ImprovementPage />);
  const panel = await screen.findByRole("region", {
    name: "A change waits for your review",
  });
  expect(await within(panel).findByText("GPT-6 Luna at low")).toBeDefined();
  expect(
    within(panel).getByText("Gemini 3.5 Flash Lite at minimal"),
  ).toBeDefined();
  expect(
    within(panel).getByText(
      "Fewer wrong approvals of claims the manual flags.",
    ),
  ).toBeDefined();
  const diff = within(panel).getByRole("group", {
    name: "Changes in proposal 1",
  });
  expect(within(diff).getByText("Refer what the manual flags.")).toBeDefined();
});

it("approves the proposal shown, after a confirmation", async () => {
  const waiting = changeProposal({ round_id: 2, proposal_id: 5 });
  const fetchMock = mockFetch(
    routes(
      [
        round({
          round_id: 2,
          stage: "change_waiting",
          progress: null,
          waiting,
        }),
      ],
      { [`POST ${OTHER}/approval`]: { round_id: 2, proposal_id: 5 } },
    ),
  );
  renderAs(<ImprovementPage />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Approve the change" }),
  );
  expect(posts(fetchMock, `${OTHER}/approval`)).toHaveLength(0);
  fireEvent.click(
    within(
      screen.getByRole("dialog", { name: "Approve the change?" }),
    ).getByRole("button", { name: "Approve the change" }),
  );
  await waitFor(() => {
    expect(posts(fetchMock, `${OTHER}/approval`)).toHaveLength(1);
  });
});

it("rejects only with a reason, and shows a refusal in an alert", async () => {
  const fetchMock = mockFetch(
    routes([waitingChange()], {
      [`POST ${PROPOSAL}/rejection`]: Response.json(
        { detail: "Round 1 is running" },
        { status: 409 },
      ),
    }),
  );
  renderAs(<ImprovementPage />);
  const reject = await screen.findByRole("button", {
    name: "Reject the change",
  });
  expect(reject).toHaveProperty("disabled", true);
  fireEvent.change(screen.getByLabelText(/^Why reject it\?/), {
    target: { value: "It names a claim." },
  });
  fireEvent.click(reject);
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Round 1 is running",
  );
  const [sent] = posts(fetchMock, `${PROPOSAL}/rejection`);
  expect(JSON.parse(sent[1]?.body as string)).toEqual({
    note: "It names a claim.",
  });
});

it("shows a waiting recipe with the same diff view", async () => {
  const waiting = recipeProposal();
  mockFetch(
    routes([round({ stage: "recipe_waiting", progress: null, waiting })]),
  );
  renderAs(<ImprovementPage />);
  const panel = await screen.findByRole("region", {
    name: "A new recipe waits for your review",
  });
  const diff = within(panel).getByRole("group", {
    name: "Changes in proposal 2",
  });
  expect(within(diff).getByText("2. Look for a pattern first.")).toBeDefined();
  expect(within(panel).queryByText(/^Model/)).toBeNull();
  expect(
    within(panel).getByRole("button", { name: "Approve the recipe" }),
  ).toBeDefined();
});

it("shows Marcus no Start, Approve or Reject, and why", async () => {
  mockFetch(routes([waitingChange()]));
  renderAs(<ImprovementPage />, MARCUS);
  await screen.findByRole("region", { name: "A change waits for your review" });
  expect(
    screen.queryByRole("button", { name: /^(Start|Stop|Approve|Reject)/ }),
  ).toBeNull();
  expect(
    screen.getByText(
      /can start or stop a round of improvement\. You're signed in as Marcus/,
    ),
  ).toBeDefined();
  expect(
    screen.getByText(/can review the improver's proposals\./),
  ).toBeDefined();
});
