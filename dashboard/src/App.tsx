import { Header } from "./components/Header";
import { RequireHandler } from "./components/RequireHandler";
import { useRoute } from "./hooks";
import { ClaimPage } from "./pages/ClaimPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { InsightsPage } from "./pages/Insights";
import { ConfigurationPage } from "./pages/ConfigurationPage";
import { QueuePage } from "./pages/Queue";
import { ScoreboardPage } from "./pages/Scoreboard";
import { SettingsPage } from "./pages/SettingsPage";
import { SignInPage } from "./pages/SignInPage";
import { VersionPage } from "./pages/VersionPage";
import type { Route } from "./paths";

type HandlerRoute = Exclude<Route, { page: "sign-in" }>;

function Page({ route }: Readonly<{ route: HandlerRoute }>) {
  switch (route.page) {
    case "claim":
      return <ClaimPage key={route.claimId} claimId={route.claimId} />;
    case "configuration":
      return <ConfigurationPage />;
    case "settings":
      return <SettingsPage />;
    case "version":
      return <VersionPage key={route.number} number={route.number} />;
    case "insights":
      return <InsightsPage />;
    case "queue":
      return <QueuePage />;
    case "scoreboard":
      return <ScoreboardPage />;
    case "evaluation":
      return <EvaluationPage key={route.runId} runId={route.runId} />;
  }
}

/** The dashboard: the sign-in page, or a signed-in handler's page under the
 *  header. */
export function App() {
  const route = useRoute();
  if (route.page === "sign-in") return <SignInPage next={route.next} />;
  return (
    <RequireHandler>
      {(handler) => (
        <>
          <Header route={route} handler={handler} />
          <main>
            <Page route={route} />
          </main>
        </>
      )}
    </RequireHandler>
  );
}
