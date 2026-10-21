import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

/** Fill the environment from the env files at the repo's root, as the Python
 *  parts do: the environment wins over .env, which wins over .env.defaults.
 *  UNDERCOVER_ENV_FILES narrows the files, as tests and e2e do. */
export function loadSettings(files: string): void {
  for (const name of files.split(",")) {
    const path = fileURLToPath(new URL(name, import.meta.url));
    if (existsSync(path)) process.loadEnvFile(path);
  }
}

export function setting(name: string): string {
  const value = process.env[name];
  if (value === undefined) throw new Error(`${name} isn't set`);
  return value;
}
