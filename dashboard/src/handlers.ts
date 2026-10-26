import { useState } from "react";
import type { Handler } from "./api";

/** A handler's name, or the agent's, from the id a decision or payment names. */
export function who(id: string, handlers: Handler[]): string {
  if (id === "agent") return "UnderCover Agent";
  return handlers.find((h) => h.handler_id === id)?.name ?? id;
}

/** The handler picked in a form: the first handler until someone picks one,
 *  including when the handlers arrive after the form. */
export function useHandlerChoice(handlers: Handler[]) {
  const [picked, setPicked] = useState("");
  return [picked || (handlers[0]?.handler_id ?? ""), setPicked] as const;
}
