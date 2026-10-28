"""The platform's settings: the models the claim agent may use."""

import json
from typing import Any

from sqlalchemy import Connection, RowMapping, insert, select

from backend.db_improvement import models_allowed

JSON_COLUMNS = ("reasoning_efforts", "options")


def add_models(conn: Connection, models: list[dict[str, Any]]) -> None:
    """Store the models allowed, in the order given."""
    conn.execute(
        insert(models_allowed),
        [
            model
            | {"position": position}
            | {name: json.dumps(model[name]) for name in JSON_COLUMNS}
            for position, model in enumerate(models)
        ],
    )


def model(conn: Connection, name: str) -> dict[str, Any] | None:
    """One model allowed, by its name, or None when it isn't one."""
    found = select(models_allowed).where(models_allowed.c.model == name)
    row = conn.execute(found).mappings().first()
    return parsed(row) if row else None


def parsed(row: RowMapping) -> dict[str, Any]:
    return dict(row) | {name: json.loads(row[name]) for name in JSON_COLUMNS}


def models(conn: Connection) -> list[dict[str, Any]]:
    """The models allowed, in order, with their efforts and options parsed."""
    found = select(models_allowed).order_by(models_allowed.c.position)
    return [parsed(row) for row in conn.execute(found).mappings()]
