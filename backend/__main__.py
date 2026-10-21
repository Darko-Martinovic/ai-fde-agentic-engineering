"""Run the backend: `uv run -m backend`, on the host and port in the settings."""

import uvicorn

from settings import setting


def main() -> None:
    uvicorn.run(
        "backend.main:app",
        host=setting("BACKEND_HOST"),
        port=int(setting("BACKEND_PORT")),
        reload=setting("BACKEND_RELOAD") == "true",
        reload_dirs=["backend", "agent"],
    )


if __name__ == "__main__":
    main()
