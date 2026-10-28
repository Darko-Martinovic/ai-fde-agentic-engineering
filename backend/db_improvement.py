"""The tables for improving the claim agent: the platform's settings, the
models it may use, the versions of its configuration, the judge's grades, and
the rounds of improvement with their proposals, the improver's recipes and its
model calls."""

from sqlalchemy import Column, Float, Integer, Table, Text

from backend.schema import counter, metadata, text_column

# The platform's settings, one row for each change: the approval limit and what
# a round of improvement works to, as JSON, with who changed them and when
# (nobody for the first, seeded row). The newest row is the settings now.
platform_settings = Table(
    "platform_settings",
    metadata,
    counter("number"),
    text_column("settings"),
    text_column("changed_by", nullable=True),
    text_column("changed_at"),
    sqlite_autoincrement=True,
)

# The judge's grade on each copy in an evaluation it could grade: its score
# from 0 (F) to 3 (A), its most likely level, the probability of each check,
# and what the call cost
grades = Table(
    "grades",
    metadata,
    Column("run_id", Integer, primary_key=True),
    text_column("claim_id", primary_key=True),
    Column("grade", Float, nullable=False),
    text_column("letter"),
    Column("same_grounds", Float, nullable=False),
    Column("same_section", Float, nullable=False),
    Column("judge_cost", Float, nullable=False),
)
# The models the claim agent may use, from data/models.json, or the free model
# in MODEL_NAME alone. The reasoning efforts and the build options are JSON.
models_allowed = Table(
    "models_allowed",
    metadata,
    text_column("model", primary_key=True),
    Column("position", Integer, nullable=False),
    text_column("label"),
    text_column("provider"),
    text_column("reasoning_efforts"),
    Column("input_price", Float, nullable=False),
    Column("output_price", Float, nullable=False),
    text_column("options"),
)
# The claim agent's configuration, one row per version: its instructions, model
# and reasoning effort, the version it was proposed against, why, who proposed
# and approved it, and once a round has evaluated it, its verdict. The current
# version is the newest kept one; version 1 is seeded kept.
versions = Table(
    "versions",
    metadata,
    Column("number", Integer, primary_key=True, autoincrement=False),
    Column("instructions", Text, nullable=False),
    text_column("model"),
    text_column("reasoning_effort"),
    Column("based_on", Integer, nullable=True),
    text_column("reason"),
    text_column("proposed_by"),
    Column("round_id", Integer, nullable=True),
    text_column("approved_by", nullable=True),
    text_column("approved_at", nullable=True),
    text_column("created_at"),
    text_column("verdict", nullable=True),
    text_column("verdict_reason", nullable=True),
    text_column("decided_at", nullable=True),
)

# The improver's recipe, one row per version: the first the lab's, each later
# one proposed in a round and approved by a handler. The newest is current.
recipes = Table(
    "recipes",
    metadata,
    Column("number", Integer, primary_key=True, autoincrement=False),
    Column("recipe", Text, nullable=False),
    Column("based_on", Integer, nullable=True),
    text_column("reason"),
    text_column("proposed_by"),
    # One recipe a round at most
    Column("round_id", Integer, nullable=True, unique=True),
    text_column("approved_by", nullable=True),
    text_column("approved_at", nullable=True),
    text_column("created_at"),
)
# A round of improvement: who started it, the settings, recipe and version it
# started from, the improver's model and thread, the first evaluations the
# version needed (as JSON), where it ended up, the version it tried, and the
# verdict on it, with the held-out scores before and after (as JSON)
rounds = Table(
    "rounds",
    metadata,
    counter("round_id"),
    text_column("started_by"),
    text_column("started_at"),
    Column("settings_number", Integer, nullable=False),
    Column("recipe_number", Integer, nullable=False),
    Column("version_before", Integer, nullable=False),
    text_column("improver_model"),
    text_column("thread_id"),
    text_column("first_evaluations"),
    text_column("status"),
    text_column("stopped_by", nullable=True),
    text_column("stop_reason", nullable=True),
    text_column("finished_at", nullable=True),
    Column("version_tried", Integer, nullable=True),
    text_column("verdict", nullable=True),
    text_column("verdict_reason", nullable=True),
    text_column("scores_before", nullable=True),
    text_column("scores_after", nullable=True),
    sqlite_autoincrement=True,
)
# What the improver proposed in a round, a change to the configuration or a
# new recipe (as JSON), its reason, and a handler's review of it
proposals = Table(
    "proposals",
    metadata,
    counter("proposal_id"),
    Column("round_id", Integer, nullable=False),
    text_column("kind"),
    text_column("proposed"),
    text_column("reason"),
    text_column("proposed_at"),
    text_column("review", nullable=True),
    text_column("reviewed_by", nullable=True),
    text_column("reviewed_at", nullable=True),
    text_column("review_note", nullable=True),
    sqlite_autoincrement=True,
)
# Each of the improver's model calls, with its round
improver_calls = Table(
    "improver_calls",
    metadata,
    counter("call_id"),
    Column("round_id", Integer, nullable=False),
    text_column("model"),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cost", Float, nullable=False),
    Column("seconds", Float, nullable=False),
    text_column("recorded_at"),
    sqlite_autoincrement=True,
)
