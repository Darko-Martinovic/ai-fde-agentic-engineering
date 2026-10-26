import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ClaimPage } from "./ClaimPage";
import { calledWith, claim, claimRoutes, decision, mockFetch } from "./testing";

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
  render(<ClaimPage claimId="CLM-1001" />);
  const button = await screen.findByRole("button", {
    name: "Sign off $1,150.00",
  });
  await screen.findByRole("option", { name: /Marcus Oyelaran/ });
  fireEvent.change(screen.getByLabelText("Handler"), {
    target: { value: "HND-02" },
  });
  table["GET /api/claims/CLM-1001"] = claim({
    status: "in_progress",
    decisions: [
      decision({
        review: "signed_off",
        reviewed_by: "HND-02",
        reviewed_at: "2026-10-19T15:05:00Z",
      }),
    ],
  });
  fireEvent.click(button);
  expect(
    await screen.findByText(/Signed off by Marcus Oyelaran/),
  ).toBeDefined();
  expect(screen.getByText("Waiting for the agent to pay it.")).toBeDefined();
  const review = fetchMock.mock.calls.find(
    ([, init]) => init?.method === "POST",
  );
  expect(JSON.parse(review?.[1]?.body as string)).toEqual({
    handler_id: "HND-02",
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
  render(<ClaimPage claimId="CLM-1001" />);
  const reject = await screen.findByRole("button", { name: "Reject" });
  await screen.findByRole("option", { name: /Dana Whitfield/ });
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
    handler_id: "HND-01",
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
  render(<ClaimPage claimId="CLM-1001" />);
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
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("The bill needs checking.")).toBeDefined();
  await screen.findByRole("option", { name: /Dana Whitfield/ });
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
    handler_id: "HND-01",
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
        { detail: "Handler HND-01 not found" },
        { status: 404 },
      ),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByRole("option", { name: /Dana Whitfield/ });
  fireEvent.click(
    await screen.findByRole("button", { name: "Sign off $1,150.00" }),
  );
  expect(await screen.findByText("Handler HND-01 not found")).toBeDefined();
});

it("lets a handler decide a claim left for them", async () => {
  const fetchMock = mockFetch(
    claimRoutes({
      "GET /api/claims/CLM-1001": claim({ status: "left_for_handler" }),
      "POST /api/claims/CLM-1001/handler-decision": claim(),
    }),
  );
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByRole("heading", { name: "Decide the claim" }),
  ).toBeDefined();
  await screen.findByRole("option", { name: /Dana Whitfield/ });
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
