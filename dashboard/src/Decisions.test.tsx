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
it("signs off a large payout", async () => {
  const table = claimRoutes({
    "GET /api/claims/CLM-1001": claim({
      status: "awaiting_sign_off",
      decisions: [decision()],
    }),
    "POST /api/claims/CLM-1001/sign-off": claim(),
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
    status: "decided",
    decisions: [decision()],
    payment: {
      amount: 1150,
      authorized_by: "HND-02",
      paid_at: "2026-10-19T15:05:00Z",
    },
  });
  fireEvent.click(button);
  expect(
    await screen.findByText(/authorized by Marcus Oyelaran/),
  ).toBeDefined();
  const signOff = fetchMock.mock.calls.find(
    ([, init]) => init?.method === "POST",
  );
  expect(signOff?.[1]?.body).toBe('{"handler_id":"HND-02"}');
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
    "POST /api/claims/CLM-1001/resolution": claim(),
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
    expect(calledWith(fetchMock, "POST /api/claims/CLM-1001/resolution")).toBe(
      true,
    );
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
      "POST /api/claims/CLM-1001/sign-off": Response.json(
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
