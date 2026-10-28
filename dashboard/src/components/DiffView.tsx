import type { DiffLine, Hunk } from "../api";

const MARKS = { added: "+", removed: "−", context: " " } as const;
const SAID = { added: "Added", removed: "Removed", context: "" } as const;

/** A stretch's lines, each keyed by where it is, since the same line can
 *  appear twice in one stretch. */
function numbered(hunk: Hunk): { line: DiffLine; key: string }[] {
  return hunk.lines.map((line, position) => ({
    line,
    key: `${hunk.heading}:${String(position)}`,
  }));
}

/** The lines a version or a recipe changed: each changed stretch with the
 *  lines around it, additions in green and removals in red, each marked with
 *  a sign and a word for screen readers as well as a color. */
export function DiffView({
  changes,
  label,
}: Readonly<{ changes: Hunk[]; label: string }>) {
  if (changes.length === 0) {
    return <p className="muted">No change to the text.</p>;
  }
  return (
    <div className="diff" role="group" aria-label={label}>
      {changes.map((hunk) => (
        <div className="diff__hunk" key={hunk.heading}>
          {numbered(hunk).map(({ line, key }) => (
            <div key={key} className={`diff__line diff__line--${line.kind}`}>
              <span className="diff__mark" aria-hidden="true">
                {MARKS[line.kind]}
              </span>
              {SAID[line.kind] && (
                <span className="visually-hidden">{SAID[line.kind]}: </span>
              )}
              <span className="diff__text">{line.text || " "}</span>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
