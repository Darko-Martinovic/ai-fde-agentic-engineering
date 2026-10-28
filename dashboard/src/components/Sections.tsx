import { useCallback, useState } from "react";
import { api, sectionOf, type SectionTitle, type Step } from "../api";
import { ErrorNote, Loading, Markdown, Panel } from "./elements";
import { sectionName } from "../format";
import { usePoll } from "../hooks";

/** The sections the agent read, once each, in the order it first read them. */
function sectionsRead(steps: Step[]): SectionTitle[] {
  const read = steps.filter((step) => step.kind === "section").map(sectionOf);
  return read.filter(
    (section, index) =>
      read.findIndex(
        (other) =>
          other.document === section.document &&
          other.number === section.number,
      ) === index,
  );
}

function SectionText({ section }: Readonly<{ section: SectionTitle }>) {
  const { document, number } = section;
  const text = usePoll(
    useCallback(
      (signal: AbortSignal) => api.readSection(document, number, signal),
      [document, number],
    ),
    null,
  );
  if (text.error)
    return <ErrorNote message={text.error} onRetry={text.reload} />;
  if (text.data === null) return <Loading label="Loading the section" />;
  return <Markdown text={text.data.text} />;
}

function SectionItem({ section }: Readonly<{ section: SectionTitle }>) {
  const [open, setOpen] = useState(false);
  return (
    <li>
      <details
        onToggle={(event) => {
          setOpen(event.currentTarget.open);
        }}
      >
        <summary>{sectionName(section)}</summary>
        {open && <SectionText section={section} />}
      </details>
    </li>
  );
}

export function SectionsPanel({ steps }: Readonly<{ steps: Step[] | null }>) {
  const sections = sectionsRead(steps ?? []);
  if (sections.length === 0) return null;
  return (
    <Panel title="Sections read" className="panel--sections">
      <ul className="sections-read">
        {sections.map((section) => (
          <SectionItem
            key={`${section.document}-${String(section.number)}`}
            section={section}
          />
        ))}
      </ul>
    </Panel>
  );
}
