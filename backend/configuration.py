"""The claim agent's configuration, in versions: the version the claim agent
runs as, which holds no scores, and for the Configuration page every version
with what it changed from the one it was based on and its held-out scores."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import Connection, RowMapping

from backend import diffs
from backend.api import Db, found
from backend.callers import AGENT, HANDLER
from backend.store import platform_settings, versions
from backend.version_models import (
    NO_EFFORT,
    Configuration,
    ModelAllowed,
    Verdict,
    Version,
    VersionConfig,
    VersionDetails,
    VersionStatus,
)
from backend.version_scores import held_out_accuracy_and_grade

router = APIRouter(prefix="/api")


def load(conn: Connection, number: int) -> RowMapping:
    return found(versions.version(conn, number), "Version", str(number))


def status(row: RowMapping, current: int) -> VersionStatus:
    if row["number"] == current:
        return VersionStatus.CURRENT
    if row["verdict"] is None:
        return VersionStatus.UNDER_TEST
    if row["verdict"] == Verdict.KEPT:
        return VersionStatus.KEPT
    return VersionStatus.ROLLED_BACK


def instructions_before(conn: Connection, row: RowMapping) -> str:
    """The instructions of the version a version was based on, or none."""
    if row["based_on"] is None:
        return row["instructions"]
    return load(conn, row["based_on"])["instructions"]


def summary(
    conn: Connection,
    row: RowMapping,
    current: int,
    changes: list[diffs.Hunk] | None = None,
) -> Version:
    """A version with its status and the lines it changed, which are worked out
    here unless given."""
    if changes is None:
        changes = diffs.changes(instructions_before(conn, row), row["instructions"])
    accuracy, grade = held_out_accuracy_and_grade(conn, row["number"]) or (None, None)
    return Version.model_validate(
        dict(row)
        | {
            "status": status(row, current),
            "lines_added": diffs.counted(changes, "added"),
            "lines_removed": diffs.counted(changes, "removed"),
            "held_out_accuracy": accuracy,
            "held_out_grade": grade,
        }
    )


def models_allowed(conn: Connection) -> list[ModelAllowed]:
    return [ModelAllowed(**model) for model in platform_settings.models(conn)]


def runs_as(conn: Connection, number: int) -> VersionConfig:
    """A version as the claim agent runs it, with how to build its model: its
    options, with its reasoning effort unless it runs with none of its own."""
    row = load(conn, number)
    model = platform_settings.model(conn, row["model"])
    if model is None:
        raise HTTPException(
            409, f"Version {number}'s model, {row['model']}, isn't one allowed"
        )
    effort = row["reasoning_effort"]
    options = model["options"] | (
        {} if effort == NO_EFFORT else {"reasoning_effort": effort}
    )
    return VersionConfig(
        number=number,
        instructions=row["instructions"],
        model=row["model"],
        reasoning_effort=effort,
        provider=model["provider"],
        options=options,
    )


@router.get(
    "/versions/current", operation_id="get_current_version", dependencies=[AGENT]
)
def get_current_version(conn: Db) -> VersionConfig:
    """Get the current version of the claim agent's configuration, as it runs."""
    return runs_as(conn, versions.current(conn))


@router.get("/versions/{number}", operation_id="get_version", dependencies=[AGENT])
def get_version(number: int, conn: Db) -> VersionConfig:
    """Get one version of the claim agent's configuration, as it runs."""
    return runs_as(conn, number)


@router.get("/configuration", operation_id="get_configuration", dependencies=[HANDLER])
def get_configuration(conn: Db) -> Configuration:
    """Get every version of the configuration, newest first, and the models allowed."""
    current = versions.current(conn)
    return Configuration(
        current=current,
        versions=[summary(conn, row, current) for row in versions.every(conn)],
        models_allowed=models_allowed(conn),
    )


@router.get(
    "/configuration/versions/{number}",
    operation_id="get_version_details",
    dependencies=[HANDLER],
)
def get_version_details(number: int, conn: Db) -> VersionDetails:
    """Get one version with what it changed from the version it was based on."""
    row = load(conn, number)
    before = load(conn, row["based_on"]) if row["based_on"] else None
    old = before["instructions"] if before else row["instructions"]
    changes = diffs.changes(old, row["instructions"])
    return VersionDetails.model_validate(
        summary(conn, row, versions.current(conn), changes).model_dump()
        | {
            "instructions": row["instructions"],
            "based_on_model": before["model"] if before else None,
            "based_on_reasoning_effort": before["reasoning_effort"] if before else None,
            "changes": changes,
        }
    )
