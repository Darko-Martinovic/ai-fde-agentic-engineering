import type { HandlerName, ModelAllowed, Version } from "./api";
import { when } from "./format";
import { who } from "./handlerNames";

/** A model's label from the models allowed, or its name when it isn't one. */
export function modelLabel(models: ModelAllowed[], model: string): string {
  return models.find((m) => m.model === model)?.label ?? model;
}

/** Who approved a version and when, or that nobody had to. */
export function approval(version: Version, handlers: HandlerName[]): string {
  if (!version.approved_by || !version.approved_at) return "Not needed";
  return `${who(version.approved_by, handlers)}, ${when(version.approved_at)}`;
}
