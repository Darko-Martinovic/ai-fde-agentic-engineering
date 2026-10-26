"""The steps the agent takes on each claim."""

from sqlalchemy import Connection, RowMapping, func, insert, select

from backend import db


def add(conn: Connection, claim_id: str, step: dict[str, str]) -> None:
    """Record a step, given as thread_id, kind, text and recorded_at."""
    conn.execute(insert(db.steps).values(claim_id=claim_id, **step))


def of_claim(conn: Connection, claim_id: str) -> list[RowMapping]:
    """A claim's steps, in the order they were recorded."""
    step = db.steps.c
    found = (
        select(step.thread_id, step.kind, step.text, step.recorded_at)
        .where(step.claim_id == claim_id)
        .order_by(step.step_id)
    )
    return list(conn.execute(found).mappings())


def every_step(conn: Connection) -> list[RowMapping]:
    """Every claim's steps, in the order they were recorded."""
    step = db.steps.c
    found = select(
        step.claim_id, step.thread_id, step.kind, step.text, step.recorded_at
    ).order_by(step.step_id)
    return list(conn.execute(found).mappings())


def count_of(conn: Connection, claim_id: str, kind: str) -> int:
    """How many steps of one kind a claim has, such as its failures."""
    step = db.steps.c
    found = select(func.count()).where(step.claim_id == claim_id, step.kind == kind)
    return conn.execute(found).scalar_one()
