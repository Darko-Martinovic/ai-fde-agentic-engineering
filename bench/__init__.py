"""The model comparison: runs the harness on the models and claims in
bench/plan.toml, and scores each decision against the handlers' own in
data/evals/. It is kept apart from the agent and the backend, which never see
that answer key."""
