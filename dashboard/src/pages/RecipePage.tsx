import { StateMessage } from "../components/StateMessage";
import { useCallback } from "react";
import { api, type RecipeDetails } from "../api";
import { DiffView } from "../components/DiffView";
import { Markdown, Panel } from "../components/elements";
import { PageHeader } from "../components/PageHeader";
import { when } from "../format";
import { who } from "../handlerNames";
import { usePoll } from "../hooks";
import { paths } from "../paths";

function RecipeView({ recipe }: Readonly<{ recipe: RecipeDetails }>) {
  const handlers = usePoll(api.listHandlers, null).data ?? [];
  return (
    <>
      <Panel title="What changed and why">
        <dl className="facts">
          <div>
            <dt>Based on</dt>
            <dd>
              {recipe.based_on === null ? (
                "Nothing: the first recipe"
              ) : (
                <a href={paths.recipe(recipe.based_on)}>
                  Recipe {String(recipe.based_on)}
                </a>
              )}
            </dd>
          </div>
          <div>
            <dt>Reason</dt>
            <dd>{recipe.reason}</dd>
          </div>
          <div>
            <dt>Made by</dt>
            <dd>
              {recipe.proposed_by}, {when(recipe.created_at)}
            </dd>
          </div>
          <div>
            <dt>Approved</dt>
            <dd>
              {recipe.approved_by && recipe.approved_at
                ? `${who(recipe.approved_by, handlers)}, ${when(recipe.approved_at)}`
                : "Not needed"}
            </dd>
          </div>
        </dl>
      </Panel>
      <Panel title="Changes to the recipe">
        <DiffView
          changes={recipe.changes}
          label={`Changes in recipe ${String(recipe.number)}`}
        />
      </Panel>
      <Panel title="The recipe in full">
        <Markdown text={recipe.recipe} />
      </Panel>
    </>
  );
}

/** One version of the improver's recipe: what it changed from the one before,
 *  why, and who proposed and approved it. */
export function RecipePage({ number }: Readonly<{ number: number }>) {
  const recipe = usePoll(
    useCallback(
      (signal: AbortSignal) => api.getRecipe(number, signal),
      [number],
    ),
    null,
  );
  return (
    <div className="page">
      <a className="back" href={paths.improvement}>
        Back to improvement
      </a>
      <PageHeader
        title={`Recipe ${String(number)}`}
        purpose="One version of the steps the improver follows in a round, beside the version it was based on."
      />
      {recipe.error && (
        <StateMessage
          kind="error"
          message={recipe.error}
          onRetry={recipe.reload}
        />
      )}
      {recipe.data === null && !recipe.error && (
        <StateMessage
          kind="loading"
          message={`Loading recipe ${String(number)}`}
        />
      )}
      {recipe.data && <RecipeView recipe={recipe.data} />}
    </div>
  );
}
