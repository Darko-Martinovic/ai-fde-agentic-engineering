import {
  cleanup,
  fireEvent,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SettingsPage } from "./SettingsPage";
import {
  HANDLERS,
  MARCUS,
  SETTINGS_VIEW,
  mockFetch,
  renderAs,
} from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

const ROUTES = {
  "GET /api/settings": SETTINGS_VIEW,
  "GET /api/handlers": HANDLERS,
};

it("shows each setting with its unit and who changed them last", async () => {
  mockFetch(ROUTES);
  renderAs(<SettingsPage />);
  const limit = await screen.findByRole("spinbutton", {
    name: /^Approval limit/,
  });
  expect(limit).toHaveProperty("value", "1000");
  expect(screen.getAllByText("(US dollars)")).toHaveLength(2);
  expect(
    await screen.findByText(/^Last changed by Dana Whitfield, /),
  ).toBeDefined();
  const models = screen.getByRole("table", { name: "Models allowed" });
  const luna = within(models).getAllByRole("row")[1];
  expect(within(luna).getByText("$0.10").className).toBe("numeric");
});

it("confirms the changes before it saves them, and Cancel sends nothing", async () => {
  const fetchMock = mockFetch({
    ...ROUTES,
    "PUT /api/settings": SETTINGS_VIEW,
  });
  renderAs(<SettingsPage />);
  fireEvent.change(
    await screen.findByRole("spinbutton", { name: /^Spending limit/ }),
    {
      target: { value: "0.75" },
    },
  );
  fireEvent.click(screen.getByRole("button", { name: "Save the changes" }));
  const dialog = screen.getByRole("dialog", { name: "Change the settings?" });
  const row = within(dialog).getByRole("row", {
    name: /Spending limit for each round/,
  });
  expect(within(row).getByText("$0.50")).toBeDefined();
  expect(within(row).getByText("$0.75")).toBeDefined();
  fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
  expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(
    false,
  );

  fireEvent.click(screen.getByRole("button", { name: "Save the changes" }));
  fireEvent.click(
    within(
      screen.getByRole("dialog", { name: "Change the settings?" }),
    ).getByRole("button", { name: "Change the settings" }),
  );
  await waitFor(() => {
    const sent = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "PUT",
    );
    expect(JSON.parse(sent?.[1]?.body as string)).toMatchObject({
      spending_limit: 0.75,
      approval_limit: 1000,
    });
  });
});

it("shows a refusal", async () => {
  mockFetch({
    ...ROUTES,
    "PUT /api/settings": Response.json(
      { detail: "Only a handler who can sign off" },
      { status: 403 },
    ),
  });
  renderAs(<SettingsPage />);
  fireEvent.change(
    await screen.findByRole("spinbutton", { name: /^Claim agents at once/ }),
    {
      target: { value: "10" },
    },
  );
  fireEvent.click(screen.getByRole("button", { name: "Save the changes" }));
  fireEvent.click(screen.getByRole("button", { name: "Change the settings" }));
  expect((await screen.findByRole("alert")).textContent).toBe(
    "Only a handler who can sign off",
  );
});

it("shows Marcus the settings read only, with why", async () => {
  mockFetch(ROUTES);
  renderAs(<SettingsPage />, MARCUS);
  expect(
    await screen.findByRole("spinbutton", { name: /^Approval limit/ }),
  ).toHaveProperty("readOnly", true);
  expect(screen.queryByRole("button", { name: "Save the changes" })).toBeNull();
  expect(
    screen.getByText(/can change the settings\. You're signed in as Marcus/),
  ).toBeDefined();
});

it("sets the appearance and remembers it", async () => {
  mockFetch(ROUTES);
  renderAs(<SettingsPage />);
  fireEvent.click(screen.getByRole("button", { name: "Dark" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("undercover-theme")).toBe("dark");
  fireEvent.click(screen.getByRole("button", { name: "Same as the computer" }));
  expect(document.documentElement.dataset.theme).toBeUndefined();
  await screen.findByRole("spinbutton", { name: /^Approval limit/ });
});
