import { useState } from "react";
import { readTheme, saveTheme, type Theme } from "../theme";
import { Panel } from "./elements";

const THEMES: { value: Theme; label: string }[] = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "Same as the computer" },
];

/** The dashboard's appearance, which this browser keeps. */
export function ThemeChoice() {
  const [theme, setTheme] = useState(readTheme);
  return (
    <Panel title="Appearance">
      <p className="muted">Kept in this browser only.</p>
      <div className="segmented" role="group" aria-label="Appearance">
        {THEMES.map((option) => (
          <button
            type="button"
            key={option.value}
            aria-pressed={theme === option.value}
            onClick={() => {
              saveTheme(option.value);
              setTheme(option.value);
            }}
          >
            {option.label}
          </button>
        ))}
      </div>
    </Panel>
  );
}
