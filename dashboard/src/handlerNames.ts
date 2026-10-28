import type { HandlerName } from "./api";

/** A handler's name, or the agent's, from the id a decision or payment names. */
export function who(id: string, handlers: HandlerName[]): string {
  if (id === "agent") return "UnderCover Agent";
  return handlers.find((h) => h.handler_id === id)?.name ?? id;
}
