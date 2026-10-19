import { api } from "./api";
import { ClaimPage } from "./ClaimPage";
import { Logo } from "./components";
import { usePoll, useRoute, useTheme, type Route, type Theme } from "./hooks";
import { InstructionsPage } from "./Instructions";
import { QueuePage } from "./Queue";

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "Auto" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

function Page({ route }: Readonly<{ route: Route }>) {
  switch (route.page) {
    case "claim":
      return <ClaimPage key={route.claimId} claimId={route.claimId} />;
    case "instructions":
      return <InstructionsPage />;
    case "queue":
      return <QueuePage />;
  }
}

function healthLabel(data: unknown, error: string | null): string {
  if (error) return "down";
  return data === null ? "checking" : "up";
}

function BackendStatus() {
  const health = usePoll(api.health, 10000);
  const label = healthLabel(health.data, health.error);
  return (
    <span className={`health health--${label}`}>
      <span className="health__dot" aria-hidden="true" />
      Backend: {label}
    </span>
  );
}

export function App() {
  const route = useRoute();
  const [theme, setTheme] = useTheme();

  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/">
          <Logo />
          <span>
            <strong>UnderCover</strong>
            <em>Claims desk</em>
          </span>
        </a>
        <nav className="nav" aria-label="Pages">
          <a
            href="#/"
            aria-current={route.page === "queue" ? "page" : undefined}
          >
            Queue
          </a>
          <a
            href="#/instructions"
            aria-current={route.page === "instructions" ? "page" : undefined}
          >
            Instructions
          </a>
        </nav>
        <div className="topbar__end">
          <BackendStatus />
          <div className="segmented" role="group" aria-label="Theme">
            {THEMES.map((option) => (
              <button
                type="button"
                key={option.value}
                aria-pressed={theme === option.value}
                onClick={() => {
                  setTheme(option.value);
                }}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>
      </header>
      <main>
        <Page route={route} />
      </main>
    </>
  );
}
