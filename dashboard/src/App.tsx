import type { ReactNode } from "react";
import { Header } from "./components/Header";
import { RequireHandler } from "./components/RequireHandler";
import { useRoute } from "./hooks";
import { ClaimPage } from "./pages/ClaimPage";
import { EvaluationPage } from "./pages/EvaluationPage";
import { ImprovementPage } from "./pages/ImprovementPage";
import { InsightsPage } from "./pages/Insights";
import { ConfigurationPage } from "./pages/ConfigurationPage";
import { QueuePage } from "./pages/Queue";
import { RecipePage } from "./pages/RecipePage";
import { ScoreboardPage } from "./pages/Scoreboard";
import { SettingsPage } from "./pages/SettingsPage";
import { SignInPage } from "./pages/SignInPage";
import { VersionPage } from "./pages/VersionPage";
import type { Route } from "./paths";

type HandlerRoute = Exclude<Route, { page: "sign-in" }>;
type PageWithId = Extract<
  HandlerRoute,
  { claimId: string } | { number: number } | { runId: number }
>;

/** The pages a link names alone. */
const PAGES: Record<
  Exclude<HandlerRoute, PageWithId>["page"],
  () => ReactNode
> = {
  queue: QueuePage,
  insights: InsightsPage,
  scoreboard: ScoreboardPage,
  improvement: ImprovementPage,
  configuration: ConfigurationPage,
  settings: SettingsPage,
};

function Page({ route }: Readonly<{ route: HandlerRoute }>) {
  switch (route.page) {
    case "claim":
      return <ClaimPage key={route.claimId} claimId={route.claimId} />;
    case "version":
      return <VersionPage key={route.number} number={route.number} />;
    case "recipe":
      return <RecipePage key={route.number} number={route.number} />;
    case "evaluation":
      return <EvaluationPage key={route.runId} runId={route.runId} />;
    default: {
      const Named = PAGES[route.page];
      return <Named />;
    }
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
