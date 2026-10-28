"""The judge's grades on an evaluation's copies."""

from dataclasses import asdict

from sqlalchemy import Connection, RowMapping, func, insert, select

from backend.db_improvement import grades
from backend.run_models import Grade


def add(conn: Connection, run_id: int, graded: dict[str, Grade]) -> None:
    """Record each copy's grade, by its id."""
    if graded:
        conn.execute(
            insert(grades),
            [
                {"run_id": run_id, "claim_id": claim_id} | asdict(grade)
                for claim_id, grade in graded.items()
            ],
        )


def of_run(conn: Connection, run_id: int) -> dict[str, RowMapping]:
    """An evaluation's grades, by the copy graded."""
    found = select(grades).where(grades.c.run_id == run_id)
    return {row["claim_id"]: row for row in conn.execute(found).mappings()}


def judge_cost(conn: Connection, run_ids: list[int]) -> float:
    """What the judge's grading of these runs cost."""
    found = select(func.coalesce(func.sum(grades.c.judge_cost), 0)).where(
        grades.c.run_id.in_(run_ids)
    )
    return conn.execute(found).scalar_one()
