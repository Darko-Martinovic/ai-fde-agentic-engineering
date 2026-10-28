"""The platform's settings: the approval limit, and what a round of improvement
works to (the objectives, the noise and tolerance, the spending limit and its
claim agents at once), each change a new row with who made it and when. Every
one reads them; a handler who can sign off payouts over the limit changes
them. The models the claim agent may use are listed beside them,
read only, from data/models.json."""

from typing import Annotated

from fastapi import APIRouter
from sqlalchemy import Connection

from backend.api import Db, now
from backend.models import Handler
from backend.settings_models import PlatformSettings, SettingsIn, SettingsView
from backend.signed_in import senior
from backend.store import platform_settings
from backend.version_models import ModelAllowed

router = APIRouter(prefix="/api")

Changer = Annotated[Handler, senior("change the settings")]


def view(conn: Connection) -> SettingsView:
    return SettingsView(
        settings=PlatformSettings(**platform_settings.current(conn)),
        models_allowed=[
            ModelAllowed(**model) for model in platform_settings.models(conn)
        ],
    )


@router.get("/settings", operation_id="get_settings")
def get_settings(conn: Db) -> SettingsView:
    """Get the platform's settings as they stand, and the models allowed."""
    return view(conn)


@router.put("/settings", operation_id="change_settings")
def change_settings(changed: SettingsIn, handler: Changer, conn: Db) -> SettingsView:
    """Change the platform's settings as the signed-in handler, keeping the old."""
    platform_settings.add(conn, changed.model_dump(), handler.handler_id, now())
    return view(conn)
