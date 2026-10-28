"""Rounds of improvement, their proposals, the improver's recipes and its model
calls."""

import json
from typing import Any

from sqlalchemy import Connection, RowMapping, func, insert, select, update

from backend.db_improvement import improver_calls, proposals, recipes, rounds

OPEN = "open"
JSON_COLUMNS = ("first_evaluations", "scores_before", "scores_after")


def parsed(row: RowMapping) -> dict[str, Any]:
    found = dict(row)
    for name in JSON_COLUMNS:
        if found.get(name) is not None:
            found[name] = json.loads(found[name])
    return found


def add(conn: Connection, started: dict[str, Any]) -> int:
    """Record a new round, open; return its id."""
    values = started | {
        "status": OPEN,
        "first_evaluations": json.dumps(started["first_evaluations"]),
    }
    added = insert(rounds).values(**values).returning(rounds.c.round_id)
    return conn.execute(added).scalar_one()


def round_(conn: Connection, round_id: int) -> dict[str, Any] | None:
    found = select(rounds).where(rounds.c.round_id == round_id)
    row = conn.execute(found).mappings().first()
    return parsed(row) if row else None


def every(conn: Connection) -> list[dict[str, Any]]:
    """Every round, newest first."""
    found = select(rounds).order_by(rounds.c.round_id.desc())
    return [parsed(row) for row in conn.execute(found).mappings()]


def open_ones(conn: Connection) -> list[int]:
    found = select(rounds.c.round_id).where(rounds.c.status == OPEN)
    return list(conn.execute(found).scalars())


def change(conn: Connection, round_id: int, values: dict[str, Any]) -> None:
    """Change a round's records, the scores as JSON."""
    for name in JSON_COLUMNS:
        if name in values and values[name] is not None:
            values = values | {name: json.dumps(values[name])}
    conn.execute(update(rounds).where(rounds.c.round_id == round_id).values(values))


def add_proposal(conn: Connection, proposal: dict[str, Any]) -> int:
    """Record what the improver proposed; return its id."""
    values = proposal | {"proposed": json.dumps(proposal["proposed"])}
    added = insert(proposals).values(**values).returning(proposals.c.proposal_id)
    return conn.execute(added).scalar_one()


def round_proposals(conn: Connection, round_id: int) -> list[dict[str, Any]]:
    """A round's proposals, oldest first."""
    found = (
        select(proposals)
        .where(proposals.c.round_id == round_id)
        .order_by(proposals.c.proposal_id)
    )
    return [
        dict(row) | {"proposed": json.loads(row["proposed"])}
        for row in conn.execute(found).mappings()
    ]


def review(conn: Connection, proposal_id: int, reviewed: dict[str, Any]) -> bool:
    """Record a handler's review of a proposal not yet reviewed; return whether
    this was the one review."""
    found = conn.execute(
        update(proposals)
        .where(proposals.c.proposal_id == proposal_id, proposals.c.review.is_(None))
        .values(reviewed)
    )
    return found.rowcount == 1


def try_version(conn: Connection, round_id: int, number: int) -> bool:
    """Record the version a round tries, once; return whether this was it."""
    found = conn.execute(
        update(rounds)
        .where(rounds.c.round_id == round_id, rounds.c.version_tried.is_(None))
        .values(version_tried=number)
    )
    return found.rowcount == 1


def add_recipe(conn: Connection, recipe: dict[str, Any]) -> int:
    """Record a new version of the recipe, numbered after the newest."""
    newest = conn.execute(select(func.max(recipes.c.number))).scalar_one()
    number = (newest or 0) + 1
    conn.execute(insert(recipes).values(number=number, **recipe))
    return number


def recipe(conn: Connection, number: int) -> RowMapping | None:
    found = select(recipes).where(recipes.c.number == number)
    return conn.execute(found).mappings().first()


def current_recipe(conn: Connection) -> int:
    return conn.execute(select(func.max(recipes.c.number))).scalar_one()


def every_recipe(conn: Connection) -> list[RowMapping]:
    """Every version of the recipe, newest first."""
    found = select(recipes).order_by(recipes.c.number.desc())
    return list(conn.execute(found).mappings())


def recipe_of_round(conn: Connection, round_id: int) -> int | None:
    """The recipe a round made, if it made one."""
    found = select(recipes.c.number).where(recipes.c.round_id == round_id)
    return conn.execute(found).scalar_one_or_none()


def add_improver_call(conn: Connection, round_id: int, call: dict[str, Any]) -> None:
    conn.execute(insert(improver_calls).values(round_id=round_id, **call))


def improver_cost(conn: Connection, round_id: int) -> float:
    """What a round's improver has cost."""
    found = select(func.coalesce(func.sum(improver_calls.c.cost), 0)).where(
        improver_calls.c.round_id == round_id
    )
    return conn.execute(found).scalar_one()
