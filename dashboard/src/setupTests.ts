import { afterEach, vi } from "vitest";
import { reset } from "./authStandIn";

// No unit test reaches Supabase Auth: auth.ts is the stand-in's, signed in as
// Dana Whitfield until a test signs out or in as someone else.
vi.mock("./auth", () => import("./authStandIn"));

// jsdom has <dialog> but not showModal or close: open and close it as a
// browser would, without the modal behavior jsdom can't show
// (The standards' test runs in Node, with no DOM at all.)
if (typeof HTMLDialogElement !== "undefined") {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close() {
    this.open = false;
  };
}

afterEach(() => {
  reset();
});
