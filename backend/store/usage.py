"""What the claim agents' work costs: each model call's tokens and cost, and each
spell of work on a claim, with the run it happened in, or none."""

from typing import Any

from sqlalchemy import Connection, RowMapping, func, insert, select

from backend import db


def add_model_call(conn: Connection, claim_id: str, call: dict[str, Any]) -> None:
    """Record one model call, given as thread_id, run_id, model, input_tokens,
    output_tokens, cost, seconds and recorded_at."""
    conn.execute(insert(db.model_calls).values(claim_id=claim_id, **call))


def add_work_time(conn: Connection, claim_id: str, spell: dict[str, Any]) -> None:
    """Record one spell of work, given as thread_id, run_id, started_at and
    seconds."""
    conn.execute(insert(db.work_times).values(claim_id=claim_id, **spell))


def run_model_calls(conn: Connection, run_id: int) -> RowMapping:
    """A run's model calls added up: how many, their tokens and their cost."""
    call = db.model_calls.c
    found = select(
        func.count().label("model_calls"),
        func.coalesce(func.sum(call.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(call.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(call.cost), 0).label("cost"),
    ).where(call.run_id == run_id)
    return conn.execute(found).mappings().one()


def claim_costs(conn: Connection, run_id: int) -> dict[str, float]:
    """What each claim's model calls cost in a run, by claim."""
    call = db.model_calls.c
    found = (
        select(call.claim_id, func.sum(call.cost))
        .where(call.run_id == run_id)
        .group_by(call.claim_id)
    )
    return {claim_id: cost for claim_id, cost in conn.execute(found).all()}


def claim_times(conn: Connection, run_id: int) -> dict[str, RowMapping]:
    """When each claim's first spell of work in a run started, and how many
    seconds its spells took in all, by claim."""
    spell = db.work_times.c
    found = (
        select(
            spell.claim_id,
            func.min(spell.started_at).label("started_at"),
            func.sum(spell.seconds).label("seconds"),
        )
        .where(spell.run_id == run_id)
        .group_by(spell.claim_id)
    )
    return {row["claim_id"]: row for row in conn.execute(found).mappings()}


def cost_of_runs(conn: Connection, run_ids: list[int]) -> float:
    """What the model calls in these runs cost."""
    found = select(func.coalesce(func.sum(db.model_calls.c.cost), 0)).where(
        db.model_calls.c.run_id.in_(run_ids)
    )
    return conn.execute(found).scalar_one()


def highest_cost_per_claim(conn: Connection, model: str) -> float | None:
    """The most a claim has cost, on average over a finished run's claims, in
    any finished run on a model, or None before its first."""
    run, call, worked = db.runs.c, db.model_calls.c, db.run_claims.c
    claims = (
        select(worked.run_id, func.count().label("claims"))
        .group_by(worked.run_id)
        .subquery()
    )
    costs = (
        select(call.run_id, func.sum(call.cost).label("cost"))
        .group_by(call.run_id)
        .subquery()
    )
    found = (
        select(func.max(costs.c.cost / claims.c.claims))
        .select_from(db.runs)
        .join(claims, claims.c.run_id == run.run_id)
        .join(costs, costs.c.run_id == run.run_id)
        .where(run.model == model, run.status == "finished")
    )
    return conn.execute(found).scalar_one()
