import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ConfigurationPage } from "./ConfigurationPage";
import { VersionPage } from "./VersionPage";
import {
  CONFIGURATION,
  SETTINGS_VIEW,
  HANDLERS,
  mockFetch,
  versionDetails,
} from "../testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const ROUTES = {
  "GET /api/configuration": CONFIGURATION,
  "GET /api/settings": SETTINGS_VIEW,
  "GET /api/handlers": HANDLERS,
  "GET /api/policy-wording": "# Policy Wording",
  "GET /api/configuration/versions/1": versionDetails({
    number: 1,
    instructions: "# UnderCover claim agent\n\nDecide the claim.",
  }),
  "GET /api/configuration/versions/2": versionDetails(),
};

it("shows the current version and every version with its status", async () => {
  mockFetch(ROUTES);
  render(<ConfigurationPage />);
  expect(
    screen.getByRole("heading", { level: 1, name: "Configuration" }),
  ).toBeDefined();
  expect(
    await screen.findByRole("heading", { name: "Current version: 1" }),
  ).toBeDefined();
  expect(screen.getAllByText("GPT-6 Luna").length).toBeGreaterThan(0);
  const table = screen.getByRole("table", { name: "Versions" });
  const [, newer, first] = within(table).getAllByRole("row");
  expect(within(newer).getByText("Under test")).toBeDefined();
  expect(within(newer).getByText("Gemini 3.5 Flash Lite")).toBeDefined();
  expect(within(newer).getByText("+1")).toBeDefined();
  expect(
    within(newer).getByRole("link", { name: "Version 2" }).getAttribute("href"),
  ).toBe("#/configuration/versions/2");
  expect(await within(newer).findByText(/^Dana Whitfield, /)).toBeDefined();
  expect(within(first).getByText("Current")).toBeDefined();
  expect(within(first).getByText("Not needed")).toBeDefined();
  expect(within(first).getByText("60%").className).toBe("numeric");
  expect(within(first).getByText("1.50").className).toBe("numeric");
});

it("shows a version's diff with its additions and removals marked", async () => {
  mockFetch(ROUTES);
  render(<VersionPage number={2} />);
  const diff = await screen.findByRole("group", {
    name: "Changes in version 2",
  });
  const added = within(diff).getByText("Refer what the manual flags.");
  expect(added.closest(".diff__line--added")).not.toBeNull();
  expect(within(diff).getByText("Added:")).toBeDefined();
  const removed = within(diff).getByText("Decide the claim.");
  expect(removed.closest(".diff__line--removed")).not.toBeNull();
  expect(await screen.findByText("GPT-6 Luna at low")).toBeDefined();
  expect(screen.getByText("Gemini 3.5 Flash Lite at minimal")).toBeDefined();
  expect(
    screen.getByText("Refer claims the manual flags for review."),
  ).toBeDefined();
  expect(screen.getAllByText("Under test").length).toBeGreaterThan(0);
});

it("says version 1 changed nothing", async () => {
  mockFetch({
    ...ROUTES,
    "GET /api/configuration/versions/1": versionDetails({
      number: 1,
      based_on: null,
      based_on_model: null,
      changes: [],
    }),
  });
  render(<VersionPage number={1} />);
  expect(await screen.findByText("No change to the text.")).toBeDefined();
  expect(screen.getByText("Nothing: the first version")).toBeDefined();
});

it("says when the configuration can't load", async () => {
  mockFetch({});
  render(<ConfigurationPage />);
  expect(
    await screen.findByText("No route for GET /api/configuration"),
  ).toBeDefined();
});
