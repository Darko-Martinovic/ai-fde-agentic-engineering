import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { refreshToken, refuseSignIns, signInAs } from "./authStandIn";
import {
  DANA,
  INSIGHTS,
  CONFIGURATION,
  QUEUE,
  SETTINGS_VIEW,
  calledWith,
  claim,
  versionDetails,
  mockFetch,
} from "./testing";

const ROUTES = {
  "GET /api/health": { status: "ok" },
  "GET /api/me": DANA,
  "GET /api/claims": QUEUE,
  "GET /api/dispatches/latest": null,
  "GET /api/claims/CLM-1001": claim(),
  "GET /api/settings": SETTINGS_VIEW,
  "GET /api/configuration/versions/1": versionDetails({
    number: 1,
    instructions: "# UnderCover claim agent\n\nDecide claims.",
  }),
  "GET /api/configuration": CONFIGURATION,
  "GET /api/policy-wording": "# Policy Wording",
  "GET /api/insights": INSIGHTS,
  "GET /api/evaluations": [],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.location.hash = "";
  localStorage.clear();
});

function go(hash: string) {
  window.location.hash = hash;
  fireEvent(window, new HashChangeEvent("hashchange"));
}

it("shows that the backend is up", async () => {
  mockFetch(ROUTES);
  render(<App />);
  expect(await screen.findByText("Backend: up")).toBeDefined();
});

it("shows that the backend is down", async () => {
  mockFetch({ ...ROUTES, "GET /api/health": Response.error() });
  render(<App />);
  expect(await screen.findByText("Backend: down")).toBeDefined();
});

it("moves between pages", async () => {
  mockFetch(ROUTES);
  render(<App />);
  expect(await screen.findByText("CLM-1002")).toBeDefined();

  go("#/instructions");
  expect(
    await screen.findByRole("heading", { name: "Configuration" }),
  ).toBeDefined();
  expect(
    screen
      .getByRole("link", { name: "Configuration" })
      .getAttribute("aria-current"),
  ).toBe("page");

  go("#/insights");
  expect(await screen.findByText("Straight through")).toBeDefined();
  expect(
    screen.getByRole("link", { name: "Insights" }).getAttribute("aria-current"),
  ).toBe("page");

  go("#/scoreboard");
  expect(await screen.findByText("No evaluation yet.")).toBeDefined();
  expect(
    screen
      .getByRole("link", { name: "Scoreboard" })
      .getAttribute("aria-current"),
  ).toBe("page");

  go("#/claims/CLM-1001");
  expect(
    await screen.findByText("Flight home canceled by the airline"),
  ).toBeDefined();
});

it("sends a visitor to sign in, then back to the page they asked for", async () => {
  mockFetch(ROUTES);
  signInAs(null);
  window.location.hash = "#/scoreboard";
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeDefined();
  expect(window.location.hash).toBe("#/sign-in?next=%23%2Fscoreboard");
  fireEvent(window, new HashChangeEvent("hashchange"));
  fireEvent.change(await screen.findByLabelText("Email"), {
    target: { value: "dana.whitfield@undercover.example" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  fireEvent(window, new HashChangeEvent("hashchange"));
  expect(await screen.findByText("No evaluation yet.")).toBeDefined();
  expect(window.location.hash).toBe("#/scoreboard");
});

it("shows a refused sign-in", async () => {
  mockFetch(ROUTES);
  signInAs(null);
  refuseSignIns("Invalid login credentials");
  go("#/sign-in");
  render(<App />);
  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "dana.whitfield@undercover.example" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "wrong" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Invalid login credentials",
  );
});

it("shows who is signed in, and signs out to the sign-in page", async () => {
  mockFetch(ROUTES);
  render(<App />);
  expect(await screen.findByText("Dana Whitfield")).toBeDefined();
  expect(screen.getByText("Senior Claims Handler")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  fireEvent(window, new HashChangeEvent("hashchange"));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeDefined();
});

it("sends the access token with every request", async () => {
  const fetchMock = mockFetch(ROUTES);
  render(<App />);
  expect(await screen.findByText("CLM-1002")).toBeDefined();
  const tokens = fetchMock.mock.calls.map(([, init]) =>
    new Headers(init?.headers).get("Authorization"),
  );
  expect(tokens.length).toBeGreaterThan(2);
  expect(new Set(tokens)).toEqual(
    new Set(["Bearer dana.whitfield@undercover.example-token"]),
  );
});

it("keeps the page when the access token is refreshed", async () => {
  const fetchMock = mockFetch(ROUTES);
  render(<App />);
  expect(await screen.findByText("CLM-1002")).toBeDefined();
  refreshToken();
  fetchMock.mockClear();
  go("#/scoreboard");
  expect(await screen.findByText("No evaluation yet.")).toBeDefined();
  expect(calledWith(fetchMock, "GET /api/me")).toBe(false);
  const tokens = fetchMock.mock.calls.map(([, init]) =>
    new Headers(init?.headers).get("Authorization"),
  );
  expect(tokens).toContain(
    "Bearer dana.whitfield@undercover.example-refreshed",
  );
});

it("says so when the backend doesn't accept a sign-in, without a loop", async () => {
  mockFetch({
    ...ROUTES,
    "GET /api/me": Response.json({ detail: "Sign in" }, { status: 401 }),
  });
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Your sign-in wasn't accepted by the backend.",
  );
  expect(window.location.hash).toBe("");
});

it("checks again when the backend can't be reached", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  try {
    const table: Record<string, unknown> = {
      ...ROUTES,
      "GET /api/me": Response.json({ detail: "Down" }, { status: 502 }),
    };
    mockFetch(table);
    render(<App />);
    expect(await screen.findByText("Checking who's signed in")).toBeDefined();
    table["GET /api/me"] = DANA;
    await vi.advanceTimersByTimeAsync(5000);
    expect(await screen.findByText("CLM-1002")).toBeDefined();
  } finally {
    vi.useRealTimers();
  }
});

it("says why someone who isn't a handler can't go on", async () => {
  mockFetch({
    ...ROUTES,
    "GET /api/me": Response.json(
      { detail: "someone@example.com isn't one of UnderCover's handlers" },
      { status: 403 },
    ),
  });
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "isn't one of UnderCover's handlers",
  );
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  fireEvent(window, new HashChangeEvent("hashchange"));
  expect(await screen.findByRole("heading", { name: "Sign in" })).toBeDefined();
});
