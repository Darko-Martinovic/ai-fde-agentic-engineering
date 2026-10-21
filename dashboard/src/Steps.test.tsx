import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { Step } from "./api";
import { StepsPanel } from "./Steps";

afterEach(cleanup);

const SECTION: Step = {
  thread_id: "CLM-1001-a",
  kind: "section",
  text: JSON.stringify({
    document: "manual",
    document_title: "Claims manual",
    number: 10,
    title: "Meals without receipts",
  }),
  recorded_at: "2026-10-21T10:00:00Z",
};

it("shows a section read among the steps", () => {
  render(<StepsPanel steps={[SECTION]} live={false} />);
  expect(screen.getByText("Reads a section")).toBeDefined();
  expect(
    screen.getByText("Claims manual 10. Meals without receipts"),
  ).toBeDefined();
});
