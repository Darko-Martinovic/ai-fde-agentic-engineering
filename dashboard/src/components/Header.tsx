import { api, type Handler } from "../api";
import { signOut } from "../auth";
import { usePoll, useTheme, type Theme } from "../hooks";
import { paths, type Route } from "../paths";
import { Logo } from "./elements";

const THEMES: { value: Theme; label: string }[] = [
  { value: "system", label: "Auto" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

/** The pages in the header, each with the routes that mark it current. */
const PAGES: { label: string; href: string; routes: Route["page"][] }[] = [
  { label: "Queue", href: paths.queue, routes: ["queue"] },
  { label: "Insights", href: paths.insights, routes: ["insights"] },
  {
    label: "Scoreboard",
    href: paths.scoreboard,
    routes: ["scoreboard", "evaluation"],
  },
  { label: "Instructions", href: paths.instructions, routes: ["instructions"] },
];

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

function ThemeSwitch() {
  const [theme, setTheme] = useTheme();
  return (
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
  );
}

/** Who is signed in, and a way to sign out. */
function SignedIn({ handler }: Readonly<{ handler: Handler }>) {
  return (
    <div className="signed-in">
      <span className="signed-in__who">
        <strong>{handler.name}</strong>
        <span>{handler.role}</span>
      </span>
      <button
        type="button"
        className="button button--quiet"
        onClick={() => {
          void signOut();
        }}
      >
        Sign out
      </button>
    </div>
  );
}

export function Header({
  route,
  handler,
}: Readonly<{ route: Route; handler: Handler }>) {
  return (
    <header className="topbar">
      <a className="brand" href={paths.queue}>
        <Logo />
        <span>
          <strong>UnderCover</strong>
          <em>Claims desk</em>
        </span>
      </a>
      <nav className="nav" aria-label="Pages">
        {PAGES.map((page) => (
          <a
            key={page.label}
            href={page.href}
            aria-current={page.routes.includes(route.page) ? "page" : undefined}
          >
            {page.label}
          </a>
        ))}
      </nav>
      <div className="topbar__end">
        <BackendStatus />
        <ThemeSwitch />
        <SignedIn handler={handler} />
      </div>
    </header>
  );
}
