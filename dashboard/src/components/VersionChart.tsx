import type { Round, Scores } from "../api";
import { Panel } from "./elements";

// The plot's size in SVG units, and the room around it for the axes' labels
const WIDTH = 480;
const HEIGHT = 240;
const LEFT = 56;
const RIGHT = 20;
const TOP = 30;
const BOTTOM = 54;
const TICKS = 4;

interface Point {
  version: number;
  value: number;
  kept: boolean;
}

interface Measure {
  title: string;
  axis: string;
  max: number;
  pick: (scores: Scores) => number | null;
  read: (value: number) => string;
}

const MEASURES: Measure[] = [
  {
    title: "Held-out accuracy",
    axis: "Accuracy",
    max: 1,
    pick: (scores) => scores.accuracy,
    read: (value) => `${String(Math.round(value * 100))}%`,
  },
  {
    title: "Held-out grade",
    axis: "Grade (0 to 3)",
    max: 3,
    pick: (scores) => scores.grade,
    read: (value) => value.toFixed(2),
  },
];

/** The rounds that judged the version they tried, oldest first: one place on
 *  the x axis each, the same in both charts. */
function judgedRounds(rounds: Round[]): Round[] {
  return rounds
    .filter((round) => round.version_tried !== null && round.verdict !== null)
    .reverse();
}

/** Each judged version's score, at its place, leaving out one without it. */
function pointsOf(judged: Round[], measure: Measure): (Point | null)[] {
  return judged.map((round) => {
    const value = round.scores_after ? measure.pick(round.scores_after) : null;
    if (value === null || round.version_tried === null) return null;
    return {
      version: round.version_tried,
      value,
      kept: round.verdict === "kept",
    };
  });
}

/** Version 1's score, from the latest round that started from it and judged
 *  the version it tried. */
function baselineOf(rounds: Round[], measure: Measure): number | null {
  const from = rounds.find(
    (round) => round.version_before === 1 && round.scores_before !== null,
  );
  return from?.scores_before ? measure.pick(from.scores_before) : null;
}

/** What the chart shows, in words, for a screen reader. */
function described(
  measure: Measure,
  points: (Point | null)[],
  baseline: number | null,
): string {
  const each = points
    .filter((point) => point !== null)
    .map(
      (point) =>
        `version ${String(point.version)} ${measure.read(point.value)}, ${point.kept ? "kept" : "rolled back"}`,
    );
  const first =
    baseline === null ? "" : `; version 1 ${measure.read(baseline)}`;
  return `${measure.title} of each version tried: ${each.join("; ")}${first}`;
}

function Chart({
  measure,
  points,
  baseline,
}: Readonly<{
  measure: Measure;
  points: (Point | null)[];
  baseline: number | null;
}>) {
  const plotWidth = WIDTH - LEFT - RIGHT;
  const plotHeight = HEIGHT - TOP - BOTTOM;
  const y = (value: number) => TOP + plotHeight * (1 - value / measure.max);
  const x = (index: number) =>
    LEFT + (plotWidth * (index + 1)) / (points.length + 1);
  const ticks = Array.from(
    { length: TICKS + 1 },
    (_, i) => (measure.max * i) / TICKS,
  );
  return (
    <figure className="version-chart">
      <figcaption>{measure.title}</figcaption>
      <svg
        viewBox={`0 0 ${String(WIDTH)} ${String(HEIGHT)}`}
        role="img"
        aria-label={described(measure, points, baseline)}
      >
        {ticks.map((tick) => (
          <g key={tick} className="version-chart__grid">
            <line x1={LEFT} x2={WIDTH - RIGHT} y1={y(tick)} y2={y(tick)} />
            <text
              x={LEFT - 8}
              y={y(tick)}
              textAnchor="end"
              dominantBaseline="middle"
            >
              {measure.read(tick)}
            </text>
          </g>
        ))}
        {baseline !== null && (
          <g className="version-chart__baseline">
            <line
              x1={LEFT}
              x2={WIDTH - RIGHT}
              y1={y(baseline)}
              y2={y(baseline)}
            />
            <text x={LEFT + 6} y={y(baseline) - 6}>
              Version 1, {measure.read(baseline)}
            </text>
          </g>
        )}
        {points.map(
          (point, index) =>
            point && (
              <g
                key={point.version}
                className={`version-chart__point version-chart__point--${point.kept ? "kept" : "rolled-back"}`}
              >
                <title>
                  {`Version ${String(point.version)}: ${measure.read(point.value)}, ${point.kept ? "kept" : "rolled back"}`}
                </title>
                <circle cx={x(index)} cy={y(point.value)} r={6} />
                <text x={x(index)} y={y(point.value) - 12} textAnchor="middle">
                  {measure.read(point.value)}
                </text>
                <text
                  className="version-chart__tick"
                  x={x(index)}
                  y={TOP + plotHeight + 26}
                  textAnchor="middle"
                >
                  {`v${String(point.version)}`}
                </text>
              </g>
            ),
        )}
        <text
          className="version-chart__axis"
          x={LEFT + plotWidth / 2}
          y={HEIGHT - 6}
          textAnchor="middle"
        >
          Version tried
        </text>
        <text
          className="version-chart__axis"
          transform={`translate(14 ${String(TOP + plotHeight / 2)}) rotate(-90)`}
          textAnchor="middle"
        >
          {measure.axis}
        </text>
      </svg>
    </figure>
  );
}

/** The held-out accuracy and grade of each version a round tried, one point
 *  per version in each of two charts, filled when kept and a ring when rolled
 *  back, beside version 1's dashed line. The rounds table holds the same
 *  numbers. */
export function VersionChart({ rounds }: Readonly<{ rounds: Round[] }>) {
  const judged = judgedRounds(rounds);
  return (
    <Panel title="Versions tried">
      {judged.length === 0 ? (
        <p className="muted">
          No version has been tried yet. Each round&apos;s version shows here
          once its verdict is in.
        </p>
      ) : (
        <>
          <div className="version-charts">
            {MEASURES.map((measure) => (
              <Chart
                key={measure.title}
                measure={measure}
                points={pointsOf(judged, measure)}
                baseline={baselineOf(rounds, measure)}
              />
            ))}
          </div>
          <ul className="chart-legend" aria-label="Legend">
            <li className="chart-legend__kept">Kept</li>
            <li className="chart-legend__rolled-back">Rolled back</li>
            <li className="chart-legend__baseline">Version 1</li>
          </ul>
        </>
      )}
    </Panel>
  );
}
