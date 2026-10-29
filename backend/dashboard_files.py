"""The dashboard as `npm run build` builds it into dashboard/dist, served by the
backend beside its API, so the two share one address: each file at its own
path, and index.html for any other path outside /api/, so a page of the
dashboard loads on a refresh. Without a build, and for an unknown /api/ path,
the backend answers as it did before, with its 404. FastAPI's StaticFiles has
no fallback to index.html, so this is a route of its own, added after every
API route."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from starlette.convertors import PathConvertor, register_url_convertor

from settings import ROOT

BUILD = ROOT / "dashboard" / "dist"


class DashboardPath(PathConvertor):
    """Any path but the API's, so every /api/ path answers as the API does,
    with its own 404 or 405."""

    regex = "(?!api(?:/|$)).*"


register_url_convertor("dashboard", DashboardPath())
router = APIRouter()


@router.api_route("/{path:dashboard}", methods=["GET", "HEAD"], include_in_schema=False)
def dashboard_file(path: str) -> FileResponse:
    """A file of the dashboard's build, or its index.html for any other page.
    Without a build, the backend's 404, as before."""
    index = BUILD / "index.html"
    if not index.is_file():
        raise HTTPException(404, "Not Found")
    found = (BUILD / path).resolve()
    if path and found.is_file() and found.is_relative_to(BUILD.resolve()):
        return FileResponse(found)
    return FileResponse(index)
