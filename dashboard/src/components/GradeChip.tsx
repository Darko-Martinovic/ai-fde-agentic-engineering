import type { EvaluationClaim } from "../api";
import { gradeOf, yesOrNo } from "../evaluations";

/** The judge's grade on a copy: the letter in a colored chip, the score, and
 *  whether the agent gave the same grounds and the same section as the
 *  handler; or that the judge couldn't grade it. */
export function GradeChip({ copy }: Readonly<{ copy: EvaluationClaim }>) {
  if (copy.letter === null || copy.grade === null) {
    return <span className="muted">Not graded</span>;
  }
  return (
    <span className="grade">
      <span className={`badge badge--grade-${copy.letter}`}>{copy.letter}</span>{" "}
      <span className="mono">{gradeOf(copy.grade)}</span>
      <span className="grade__checks">
        Same grounds: {yesOrNo(copy.same_grounds ?? 0)}. Same section:{" "}
        {yesOrNo(copy.same_section ?? 0)}.
      </span>
    </span>
  );
}
