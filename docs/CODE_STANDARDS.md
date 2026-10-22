# Code standards

## General

1. Keep it simple, do not overcomplicate.
2. Comments only when necessary.
3. Be concise: a short README and no emojis.
4. IMPORTANT: avoid overly defensive code. Handle exceptions only when necessary.
5. Use uv: ALWAYS `uv run`, NEVER `python3`.
6. TypeScript: strict mode, never `any`.

## Structure

7. One way to do each thing. The agent reaches the backend only through `agent/api.py` and the dashboard only through `dashboard/src/api.ts`, each with one function per backend operation, named after it. The base URL and each path are written once, there, and no other module builds a URL or sends a request.
8. Each module has one job, and its name says what it is. A module uses another through what that module is for, and never borrows its helpers. A helper two modules need goes in a module of its own. No circular imports. Tests follow the same rule: shared test helpers live in their own module, never in another test file.
9. Write a literal once. A URL, a path, a status or a message used in more than one place is named once, in the module that owns it.
10. Use the framework's own way before writing your own: FastAPI dependencies and models, LangChain's `context_schema` with `ToolRuntime` for what a tool needs to know, LangChain middleware for what happens around model and tool calls, `init_chat_model` for models, React hooks and shared components. Check the documentation for the installed version. Where we write our own instead, the plan says why.
11. A function does one job. Split one that mixes levels of detail, such as setting up a run, driving the agent and recording the result.
12. When you extend code, bring it up to these standards first. Never copy a pattern they rule out.

## The agent

13. The agent has three parts, kept apart, and their supports. `api.py` is the backend's API. `tools.py` holds every tool and the contexts the tools read. `harness.py` builds and runs the agents: their models and runs. `middleware.py` holds what happens around their model and tool calls, `tracing.py` traces them in Langfuse, and `config.py` reads the models allowed. Rules about claims and payments are enforced by the backend, whatever the agent does.
14. Instructions give an agent its goal, what it has to work from and what done looks like. They don't script its steps: it plans those itself. Anything that must always happen, or happen in a fixed order, is done by the code.

## Checked by tests

Except where marked, these hold because a test fails when they don't: `tests/test_standards.py` for the Python parts and `dashboard/src/standards.test.ts` for the dashboard and the TypeScript config. A guard that is in the way is a sign the design is wrong, never a reason to loosen the guard.

15. One owner for each service's address. In the agent, `httpx` and `/api/` paths appear only in `agent/api.py`; in the dashboard, `fetch` and `/api/` paths only in `api.ts`.
16. One name for each operation: each function in `agent/api.py` is named after a backend `operation_id`, each key of `api` in `dashboard/src/api.ts` is the same name in camelCase, and each Postman request's description starts with its operation, every operation having at least one request.
17. `backend/main.py` only puts the app together. Routes live in one router per resource (claims, records, documents, workflow, runner, insights, and later runs). All SQL lives in `backend/store/`, one module per group of tables, each function named for what it returns or does; routes and other modules call those functions, never the database. `backend/db.py` holds the schema.
18. Size: a module stays under 300 lines and a function under 40, or 120 for a React component. Past that, split it. ESLint enforces `max-lines` 300, `max-lines-per-function` 120 and `complexity` 10; ruff enforces mccabe 8; tests check each Python module's and function's length.
19. Page links are built in one place, `dashboard/src/paths.ts`, which also reads them back.
20. Tests mirror modules: a test file per module it tests, shared helpers in `conftest.py` or `dashboard/src/testing.ts`. (Checked by review.)
21. Names say what a thing is, never how it's built: no `utils`, `helpers`, `misc` or `common` modules. (Checked by review.)
22. Configuration comes from the environment, filled in from `.env` and then `.env.defaults` by `settings.py` (Python) and `settings.config.ts` (TypeScript), and the models allowed come from `models.toml`. A value can name another as `${NAME}`, so each host and port is written once. No host, port, URL, model id or price is written in code. Tests and the end-to-end run read `.env.defaults` alone, so `npm run check` never needs `.env`.
