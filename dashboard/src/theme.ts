/** The dashboard's appearance: light, dark or the same as the computer, which
 *  each browser keeps. It's set on the page as `data-theme` before the first
 *  render, so a page never flashes the other theme. */

export type Theme = "system" | "light" | "dark";
const THEME_KEY = "undercover-theme";

export function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    return saved === "light" || saved === "dark" ? saved : "system";
  } catch {
    return "system";
  }
}

/** Show the page in a theme; the computer's leaves `data-theme` off, so the
 *  styles follow `prefers-color-scheme`. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
}

/** Keep a theme for this browser and show it. */
export function saveTheme(theme: Theme): void {
  applyTheme(theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // Private windows can refuse storage; the theme still applies.
  }
}
