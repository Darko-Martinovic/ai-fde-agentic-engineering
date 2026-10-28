"""The versions of the claim agent's configuration."""

from typing import Any

from sqlalchemy import Connection, RowMapping, func, insert, select, update

from backend.db_improvement import versions
from backend.version_models import Verdict


def add(conn: Connection, version: dict[str, Any]) -> int:
    """Record a new version, numbered after the newest; return its number."""
    newest = conn.execute(select(func.max(versions.c.number))).scalar_one()
    number = (newest or 0) + 1
    conn.execute(insert(versions).values(number=number, **version))
    return number


def version(conn: Connection, number: int) -> RowMapping | None:
    found = select(versions).where(versions.c.number == number)
    return conn.execute(found).mappings().first()


def every(conn: Connection) -> list[RowMapping]:
    """Every version, newest first."""
    found = select(versions).order_by(versions.c.number.desc())
    return list(conn.execute(found).mappings())


def current(conn: Connection) -> int:
    """The current version: the newest kept one. Seeding keeps version 1, so
    there always is one."""
    kept = select(func.max(versions.c.number)).where(versions.c.verdict == Verdict.KEPT)
    number = conn.execute(kept).scalar_one()
    if number is None:
        raise RuntimeError("No version is kept: reseed with uv run -m backend.seed")
    return number


def run_on(conn: Connection, number: int) -> dict[str, Any]:
    """What a run records of the version it uses: its number, model and
    reasoning effort."""
    found = select(
        versions.c.number.label("version"),
        versions.c.model,
        versions.c.reasoning_effort,
    ).where(versions.c.number == number)
    return dict(conn.execute(found).mappings().one())


def decide(
    conn: Connection, number: int, verdict: Verdict, reason: str, at: str
) -> None:
    """Record the verdict on a version a round tried: kept, when it becomes the
    current version, or rolled back."""
    conn.execute(
        update(versions)
        .where(versions.c.number == number)
        .values(verdict=verdict, verdict_reason=reason, decided_at=at)
    )
