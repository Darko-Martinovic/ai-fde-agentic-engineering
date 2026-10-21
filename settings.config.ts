import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

/** UnderCover's settings, for the TypeScript config, as settings.py gives them
 *  to the Python parts: the environment wins over .env, which wins over
 *  .env.defaults, and a value can name another as ${NAME}. */

export const DEFAULTS_ONLY = ".env.defaults";
const ALL_FILES = ".env,.env.defaults";

export function loadSettings(
  files: string = process.env.UNDERCOVER_ENV_FILES ?? ALL_FILES,
): void {
  for (const name of files.split(",")) {
    const path = fileURLToPath(new URL(name, import.meta.url));
    if (existsSync(path)) process.loadEnvFile(path);
  }
}

export function setting(name: string): string {
  const value = process.env[name];
  if (value === undefined) throw new Error(`${name} isn't set`);
  return value.replace(/\$\{(\w+)\}/g, (_, inner: string) => setting(inner));
}
