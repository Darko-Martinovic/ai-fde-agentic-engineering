"""The tables for improving the claim agent: the platform's settings, the
models it may use and the versions of its configuration."""

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
