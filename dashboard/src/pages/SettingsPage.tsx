import { useState } from "react";
import {
  api,
  type HandlerName,
  type PlatformSettings,
  type SettingsIn,
} from "../api";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { ErrorNote, Loading, Panel } from "../components/elements";
import { ModelsAllowed } from "../components/ModelsAllowed";
import { NotAllowed } from "../components/NotAllowed";
import { PageHeader } from "../components/PageHeader";
import { ThemeChoice } from "../components/ThemeChoice";
import { clock, date } from "../format";
import { useHandler } from "../handler";
import { who } from "../handlerNames";
import { useAction, usePoll } from "../hooks";
import {
  FIELDS,
  GROUPS,
  type Field,
  type FieldKey,
  valueAt,
  withValue,
} from "../settingsFields";

type Draft = Record<FieldKey, string>;

/** The group each field is in, to name it where its label alone is ambiguous,
 *  as the noise's accuracy and the tolerance's are. */
const GROUP_OF = Object.fromEntries(
  GROUPS.flatMap((group) => group.fields.map((f) => [f.key, group.title])),
) as Record<FieldKey, string>;

function draftOf(settings: SettingsIn): Draft {
  return Object.fromEntries(
    FIELDS.map((field) => [field.key, String(valueAt(settings, field.key))]),
  ) as Draft;
}

/** The settings the draft would make, and the fields it changes. */
function changesIn(settings: SettingsIn, draft: Draft) {
  let changed = settings;
  const fields: Field[] = [];
  for (const field of FIELDS) {
    const value = Number(draft[field.key]);
    if (value !== valueAt(settings, field.key)) {
      changed = withValue(changed, field.key, value);
      fields.push(field);
    }
  }
  return { changed, fields };
}

function LastChange({
  settings,
  handlers,
}: Readonly<{ settings: PlatformSettings; handlers: HandlerName[] }>) {
  const at = `${date(settings.changed_at)} at ${clock(settings.changed_at)}`;
  return (
    <p className="last-change">
      {settings.changed_by
        ? `Last changed by ${who(settings.changed_by, handlers)}, ${at}.`
        : `As seeded from data/, ${at}.`}
    </p>
  );
}

function ChangesTable({
  settings,
  changed,
  fields,
}: Readonly<{ settings: SettingsIn; changed: SettingsIn; fields: Field[] }>) {
  return (
    <table className="changes" aria-label="The changes">
      <thead>
        <tr>
          <th scope="col">Setting</th>
          <th scope="col" className="numeric">
            Now
          </th>
          <th scope="col" className="numeric">
            New
          </th>
        </tr>
      </thead>
      <tbody>
        {fields.map((field) => (
          <tr key={field.key}>
            <td>{`${GROUP_OF[field.key]}: ${field.label}`}</td>
            <td className="numeric">
              {field.read(valueAt(settings, field.key))}
            </td>
            <td className="numeric">
              {field.read(valueAt(changed, field.key))}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SettingField({
  field,
  value,
  locked,
  onChange,
}: Readonly<{
  field: Field;
  value: string;
  locked: boolean;
  onChange: (value: string) => void;
}>) {
  return (
    <label className="field">
      <span>
        {field.label} <span className="field__unit">({field.unit})</span>
      </span>
      <input
        type="number"
        required
        min={field.min}
        max={field.max}
        step={field.step}
        inputMode="decimal"
        value={value}
        readOnly={locked}
        onChange={(event) => {
          onChange(event.target.value);
        }}
      />
    </label>
  );
}

function SettingsForm({
  settings,
  onSaved,
}: Readonly<{ settings: PlatformSettings; onSaved: () => void }>) {
  const handler = useHandler();
  const locked = !handler.can_approve_over_limit;
  const [draft, setDraft] = useState(() => draftOf(settings));
  const [confirming, setConfirming] = useState(false);
  const { busy, error, run } = useAction(onSaved);
  const { changed, fields } = changesIn(settings, draft);
  return (
    <form
      aria-label="The platform's settings"
      onSubmit={(event) => {
        event.preventDefault();
        setConfirming(true);
      }}
    >
      <div className="settings-grid">
        {GROUPS.map((group) => (
          <Panel
            key={group.title}
            title={group.title}
            className="settings-group"
          >
            <p>{group.purpose}</p>
            <fieldset className="settings-group__fields">
              <legend className="visually-hidden">{group.title}</legend>
              {group.fields.map((field) => (
                <SettingField
                  key={field.key}
                  field={field}
                  value={draft[field.key]}
                  locked={locked}
                  onChange={(value) => {
                    setDraft({ ...draft, [field.key]: value });
                  }}
                />
              ))}
            </fieldset>
          </Panel>
        ))}
      </div>
      {locked ? (
        <NotAllowed action="change the settings" />
      ) : (
        <div className="form-actions">
          <button
            type="submit"
            className="button button--primary"
            disabled={busy || fields.length === 0}
          >
            Save the changes
          </button>
        </div>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <ConfirmDialog
        open={confirming}
        title="Change the settings?"
        confirmLabel="Change the settings"
        onCancel={() => {
          setConfirming(false);
        }}
        onConfirm={() => {
          setConfirming(false);
          run(() => api.changeSettings(changed));
        }}
      >
        <ChangesTable settings={settings} changed={changed} fields={fields} />
      </ConfirmDialog>
    </form>
  );
}

/** The platform's settings: what every signed-in handler sees, and a handler
 *  who can sign off payouts over the limit changes, after a confirmation. */
export function SettingsPage() {
  const view = usePoll(api.getSettings, null);
  const handlers = usePoll(api.listHandlers, null);
  return (
    <div className="page">
      <PageHeader
        title="Settings"
        purpose="What the platform works to: the approval limit, and what each round of improvement aims for and may spend. Each change is kept with who made it."
      />
      {view.error && <ErrorNote message={view.error} onRetry={view.reload} />}
      {view.data === null && !view.error && (
        <Loading label="Loading the settings" />
      )}
      {view.data && (
        <>
          <LastChange
            settings={view.data.settings}
            handlers={handlers.data ?? []}
          />
          <SettingsForm
            key={view.data.settings.number}
            settings={view.data.settings}
            onSaved={view.reload}
          />
          <ModelsAllowed models={view.data.models_allowed} />
        </>
      )}
      <ThemeChoice />
    </div>
  );
}
