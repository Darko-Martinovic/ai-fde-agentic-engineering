import type { EvaluationClaim } from "../api";
import { NOT_GRADED, gradeOf, yesOrNo } from "../evaluations";

/** The judge's grade on a copy: the letter in a colored chip, the score, and
 *  whether the agent gave the same grounds and the same section as the
 *  handler; or that the judge couldn't grade it. */
export function GradeChip({ copy }: Readonly<{ copy: EvaluationClaim }>) {
  const { grade, letter, same_grounds: grounds, same_section: section } = copy;
  if (
    grade === null ||
    letter === null ||
    grounds === null ||
    section === null
  ) {
    return <span className="muted">{NOT_GRADED}</span>;
  }
  return (
    <span className="grade">
      <span className={`badge badge--grade-${letter}`}>{letter}</span>{" "}
      <span className="mono">{gradeOf(grade)}</span>
      <span className="grade__checks">
        Same grounds: {yesOrNo(grounds)}. Same section: {yesOrNo(section)}.
      </span>
    </span>
  );
}
