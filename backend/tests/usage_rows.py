"""The model calls and spells of work recorded on a claim, read straight from the
database, for the tests."""

from sqlalchemy import select

from backend import db


def rows(table, claim_id):
    with db.engine().connect() as conn:
        found = select(table).where(table.c.claim_id == claim_id)
        return [dict(row) for row in conn.execute(found).mappings()]


def model_calls(claim_id):
    return rows(db.model_calls, claim_id)


def work_times(claim_id):
    return rows(db.work_times, claim_id)
