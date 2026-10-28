import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ClaimPage } from "../pages/ClaimPage";
import {
  MARCUS,
  calledWith,
  claim,
  claimRoutes,
  decision,
  mockFetch,
  renderAs,
} from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const HELD = claim({ status: "awaiting_sign_off", decisions: [decision()] });

it("signs off a held payout, which goes back to the agent to pay", async () => {
  const table = claimRoutes({
    "GET /api/claims/CLM-1001": HELD,
    "POST /api/claims/CLM-1001/review": claim(),
  });
  const fetchMock = mockFetch(table);
  renderAs(<ClaimPage claimId="CLM-1001" />);
  const button = await screen.findByRole("button", {
    name: "Sign off $1,150.00",
  });
  table["GET /api/claims/CLM-1001"] = claim({
    status: "in_progress",
    decisions: [
      decision({
        review: "signed_off",
        reviewed_by: "HND-01",
        reviewed_at: "2026-10-19T15:05:00Z",
      }),
    ],
  });
  fireEvent.click(button);
  expect(await screen.findByText(/Signed off by Dana Whitfield/)).toBeDefined();
  expect(screen.getByText("Waiting for the agent to pay it.")).toBeDefined();
  const review = fetchMock.mock.calls.find(
    ([, init]) => init?.method === "POST",
  );
  expect(JSON.parse(review?.[1]?.body as string)).toEqual({
    approved: true,
    note: "",
  });
});

it("rejects a held payout with a note for the agent", async () => {
  const table = claimRoutes({
    "GET /api/claims/CLM-1001": HELD,
    "POST /api/claims/CLM-1001/review": claim(),
  });
  const fetchMock = mockFetch(table);
  renderAs(<ClaimPage claimId="CLM-1001" />);
  const reject = await screen.findByRole("button", { name: "Reject" });
  expect(reject).toHaveProperty("disabled", true);
  fireEvent.change(screen.getByLabelText("Note for the agent"), {
    target: { value: " The suit is limited to $300.00. " },
  });
  expect(reject).toHaveProperty("disabled", false);
  table["GET /api/claims/CLM-1001"] = claim({
    status: "in_progress",
    decisions: [
      decision({
        review: "rejected",
        reviewed_by: "HND-01",
        reviewed_at: "2026-10-19T15:05:00Z",
        review_note: "The suit is limited to $300.00.",
      }),
    ],
  });
  fireEvent.click(reject);
  expect(
    await screen.findByText(
      "Waiting for the agent to look at the claim again.",
    ),
  ).toBeDefined();
  expect(screen.queryByText("Waiting for the agent to pay it.")).toBeNull();
  expect(
    await screen.findByText(
      /Rejected by Dana Whitfield at .*: The suit is limited to \$300\.00\./,
    ),
  ).toBeDefined();
  const review = fetchMock.mock.calls.find(
    ([, init]) => init?.method === "POST",
  );
  expect(JSON.parse(review?.[1]?.body as string)).toEqual({
    approved: false,
    note: "The suit is limited to $300.00.",
  });
});

it("shows a payment with its sign-off", async () => {
  mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({
        status: "decided",
        decisions: [
          decision({
            review: "signed_off",
            reviewed_by: "HND-01",
            reviewed_at: "2026-10-19T15:05:00Z",
          }),
        ],
        payment: {
          amount: 1150,
          authorized_by: "HND-01",
          paid_at: "2026-10-19T15:05:02Z",
          signed_off_at: "2026-10-19T15:05:00Z",
        },
      }),
    }),
  );
  renderAs(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText(
      /Paid \$1,150\.00, signed off by Dana Whitfield at/,
    ),
  ).toBeDefined();
});

it("lets a handler decide a referral", async () => {
  const table = claimRoutes({
    "GET /api/claims/CLM-1001": claim({
      status: "referred",
      decisions: [
        decision({
          decision: "refer",
          payout: 0,
          reasons: "The bill needs checking.",
        }),
      ],
    }),
    "POST /api/claims/CLM-1001/handler-decision": claim(),
  });
  const fetchMock = mockFetch(table);
  renderAs(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("The bill needs checking.")).toBeDefined();
  const submit = screen.getByRole("button", { name: "Record the decision" });
  expect(submit).toHaveProperty("disabled", true);

  fireEvent.change(screen.getByLabelText("Payout in US dollars"), {
    target: { value: "1350" },
  });
  fireEvent.change(screen.getByLabelText("Reasons"), {
    target: { value: "Covered emergency treatment." },
  });
  const approve = screen.getByRole("button", {
    name: "Approve and pay $1,350.00",
  });
  expect(approve).toHaveProperty("disabled", false);
  fireEvent.click(approve);
  await waitFor(() => {
    expect(
      calledWith(fetchMock, "POST /api/claims/CLM-1001/handler-decision"),
    ).toBe(true);
  });
  const call = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
  expect(JSON.parse(call?.[1]?.body as string)).toEqual({
    decision: "approve",
    payout: 1350,
    reasons: "Covered emergency treatment.",
  });

  fireEvent.click(screen.getByLabelText("Decline"));
  expect(screen.queryByLabelText("Payout in US dollars")).toBeNull();
  expect(
    screen.getByRole("button", { name: "Record the decision" }),
  ).toHaveProperty("disabled", false);
});

it("shows why a handler's action failed", async () => {
  mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({
        status: "awaiting_sign_off",
        decisions: [decision()],
      }),
      "POST /api/claims/CLM-1001/review": Response.json(
        { detail: "Claim CLM-1001 has just been reviewed" },
        { status: 409 },
      ),
    }),
  );
  renderAs(<ClaimPage claimId="CLM-1001" />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Sign off $1,150.00" }),
  );
  expect(
    await screen.findByText("Claim CLM-1001 has just been reviewed"),
  ).toBeDefined();
});

it("lets a handler decide a claim left for them", async () => {
  const fetchMock = mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({ status: "left_for_handler" }),
      "POST /api/claims/CLM-1001/handler-decision": claim(),
    }),
  );
  renderAs(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByRole("heading", { name: "Decide the claim" }),
  ).toBeDefined();
  fireEvent.click(screen.getByLabelText("Decline"));
  fireEvent.change(screen.getByLabelText("Reasons"), {
    target: { value: "Not covered." },
  });
  fireEvent.click(screen.getByRole("button", { name: "Record the decision" }));
  await waitFor(() => {
    expect(
      calledWith(fetchMock, "POST /api/claims/CLM-1001/handler-decision"),
    ).toBe(true);
  });
});

it("names a copy's evaluation and offers no review of its held payout", async () => {
  mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({
        ...HELD,
        claim_id: "CLM-1112-E4",
        evaluation_id: 4,
        copy_of: "CLM-1112",
      }),
    }),
  );
  renderAs(<ClaimPage claimId="CLM-1001" />);
  const link = await screen.findByRole("link", { name: "evaluation #4" });
  expect(link.getAttribute("href")).toBe("#/scoreboard/4");
  expect(screen.getByText(/A copy of CLM-1112 in/)).toBeDefined();
  expect(
    screen.getByText(
      "Held for sign-off. In an evaluation this counts as finished, and a copy can't be signed off.",
    ),
  ).toBeDefined();
  expect(screen.queryByRole("button", { name: /Sign off/ })).toBeNull();
});

it("offers no handler's decision on a copy left for a handler", async () => {
  mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({
        status: "referred",
        decisions: [decision({ decision: "refer", payout: 0 })],
        evaluation_id: 4,
        copy_of: "CLM-1110",
      }),
    }),
  );
  renderAs(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText(/a handler doesn't decide a copy/),
  ).toBeDefined();
  expect(
    screen.queryByRole("button", {
      name: /Record the decision|Approve and pay/,
    }),
  ).toBeNull();
});

it("tells a handler who can't sign off over the limit why there's no review", async () => {
  mockFetch(claimRoutes({ "GET /api/claims/CLM-1001": HELD }));
  renderAs(<ClaimPage claimId="CLM-1001" />, MARCUS);
  expect(
    await screen.findByText(
      "Only a handler who can sign off payouts over the approval limit can review this payout. You're signed in as Marcus Oyelaran, who can't.",
    ),
  ).toBeDefined();
  expect(screen.queryByRole("button", { name: /Sign off|Reject/ })).toBeNull();
  expect(screen.queryByLabelText("Note for the agent")).toBeNull();
});
