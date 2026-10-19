# Status

The pilot is being built from `docs/PLAN.md`. Phase 1 of 6 is done.

## Built

- `backend/`: UnderCover's records in SQLite, seeded from `data/` on first use, with read operations for the claims queue, one claim, a policy with its plan and add-ons, a customer with their claim history, the policy wording, the agent's instructions (`backend/instructions.md`) and the handlers. Every claim starts `waiting`. The backend never reads `data/evals/` or `data/security/`.
- `agent/`: still the hello-world skeleton, with one tool that calls the health route.
- `dashboard/`: still one page that shows whether the backend is up.
- `e2e/`: one test of that page.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173. The API is documented at http://localhost:8000/docs.
- The database is `backend/undercover.db`, or the file named in `UNDERCOVER_DB`. `uv run -m backend.seed` resets it to the data in `data/`.
- `npm run check` runs every check.
