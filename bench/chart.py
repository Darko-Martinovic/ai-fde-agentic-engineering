"""The comparison's chart: for each trial, the share of claims with the right
decision and the right payout, with the cost and time per claim beside it. A
plain SVG, in light and dark, for results.md."""

from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from statistics import mean
from typing import Protocol

WIDTH = 760
ROW = 64
TOP = 56
LABELS = 220
BARS = 340
BAR = 14
NOTES = LABELS + BARS + 60

STYLE = """
  .text { fill: #0b0b0b; font: 13px system-ui, sans-serif; }
  .muted { fill: #52514e; font: 12px system-ui, sans-serif; }
  .grid { stroke: #e5e4e0; stroke-width: 1; }
  .decision { fill: #2a78d6; }
  .payout { fill: #eb6834; }
  @media (prefers-color-scheme: dark) {
    .text { fill: #f0efec; }
    .muted { fill: #c3c2b7; }
    .grid { stroke: #3a3936; }
    .decision { fill: #3987e5; }
    .payout { fill: #d95926; }
  }
"""


class Trial(Protocol):
    @property
    def label(self) -> str: ...
    @property
    def claims(self) -> str: ...
    @property
    def worked(self) -> int: ...
    @property
    def runs(self) -> int: ...
    @property
    def decisions(self) -> list[float]: ...
    @property
    def payouts(self) -> list[float]: ...
    @property
    def cost(self) -> float: ...
    @property
    def seconds(self) -> float: ...


@dataclass(frozen=True)
class Bar:
    css: str
    share: float
    y: float


def bar(mark: Bar) -> str:
    """A bar from the baseline, with its value at its end."""
    length = max(BARS * mark.share / 100, 2)
    return (
        f'<rect class="{mark.css}" x="{LABELS}" y="{mark.y}" width="{length:.1f}" '
        f'height="{BAR}" rx="3"/>'
        f'<text class="muted" x="{LABELS + length + 6:.1f}" y="{mark.y + BAR - 2}">'
        f"{mark.share:.0f}%</text>"
    )


def price(cost: float) -> str:
    return f"${cost:.4f} a claim" if cost else "Free"


def row(trial: Trial, top: float) -> str:
    runs = "run" if trial.runs == 1 else "runs"
    return "".join(
        [
            f'<text class="text" x="0" y="{top + 16}">{escape(trial.label)}</text>',
            f'<text class="muted" x="0" y="{top + 34}">{trial.claims} claims '
            f"({trial.worked}), {trial.runs} {runs}</text>",
            bar(Bar("decision", mean(trial.decisions), top + 4)),
            bar(Bar("payout", mean(trial.payouts), top + 4 + BAR + 2)),
            f'<text class="text" x="{NOTES}" y="{top + 16}">{price(trial.cost)}</text>',
            f'<text class="muted" x="{NOTES}" y="{top + 34}">'
            f"{trial.seconds:.0f} s a claim</text>",
        ]
    )


def axis(height: float) -> str:
    """Grid lines at 0, 50 and 100%, labeled below the rows."""
    lines = []
    for share in (0, 50, 100):
        x = LABELS + BARS * share / 100
        lines.append(
            f'<line class="grid" x1="{x}" y1="{TOP - 8}" x2="{x}" y2="{height - 24}"/>'
            f'<text class="muted" x="{x}" y="{height - 8}" text-anchor="middle">'
            f"{share}%</text>"
        )
    return "".join(lines)


def legend() -> str:
    return (
        f'<rect class="decision" x="{LABELS}" y="8" width="12" height="12" rx="2"/>'
        f'<text class="text" x="{LABELS + 18}" y="18">Decision right</text>'
        f'<rect class="payout" x="{LABELS + 140}" y="8" width="12" height="12" rx="2"/>'
        f'<text class="text" x="{LABELS + 158}" y="18">Payout right</text>'
    )


def chart(trials: Sequence[Trial]) -> str:
    """The chart as an SVG document."""
    height = TOP + ROW * len(trials) + 32
    rows = "".join(row(trial, TOP + ROW * index) for index, trial in enumerate(trials))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" '
        f'viewBox="0 0 {WIDTH} {height}" role="img" aria-label="Share of claims '
        f'with the right decision and payout, by model">'
        f"<style>{STYLE}</style>{axis(height)}{legend()}{rows}</svg>\n"
    )
