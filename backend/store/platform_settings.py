"""The platform's settings, kept as a history of changes, and the models the
claim agent may use."""

import json
from typing import Any

from sqlalchemy import Connection, RowMapping, insert, select

from backend.db_improvement import models_allowed, platform_settings

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


def add(
    conn: Connection, settings: dict[str, Any], changed_by: str | None, at: str
) -> None:
    """Record the settings as they now stand, a new row."""
    conn.execute(
        insert(platform_settings).values(
            settings=json.dumps(settings), changed_by=changed_by, changed_at=at
        )
    )


def row(conn: Connection, number: int) -> dict[str, Any]:
    """One row of the settings' history, as a round keeps it."""
    found = select(platform_settings).where(platform_settings.c.number == number)
    return settings_of(conn.execute(found).mappings().one())


def current(conn: Connection) -> dict[str, Any]:
    """The settings as they stand, the newest row, with its number and who
    changed them when."""
    found = (
        select(platform_settings).order_by(platform_settings.c.number.desc()).limit(1)
    )
    return settings_of(conn.execute(found).mappings().one())


def settings_of(found: RowMapping) -> dict[str, Any]:
    """A row of settings, with its number and who changed them when."""
    return json.loads(found["settings"]) | {
        "number": found["number"],
        "changed_by": found["changed_by"],
        "changed_at": found["changed_at"],
    }
