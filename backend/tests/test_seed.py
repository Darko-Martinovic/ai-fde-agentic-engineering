import shutil

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, delete, func, inspect, select

from backend import db, seed
from backend.store import evaluations
from backend.tests.direct_changes import count_claims, set_status

# The queue's 25 claims and CLM-1901, the security team's
QUEUE = 26


def test_seeds_from_the_seed_files_alone(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for name in seed.SEED_FILES:
        shutil.copy(seed.DATA_DIR / name, data / name)
    (data / seed.SECURITY).mkdir()
    for name in seed.SECURITY_FILES:
        shutil.copy(seed.DATA_DIR / seed.SECURITY / name, data / seed.SECURITY / name)
    monkeypatch.setattr(seed, "DATA_DIR", data)
    seed.reset()
    assert count_claims() == QUEUE


def test_seed_files_leave_out_the_answer_key():
    assert not any("evals" in name for name in seed.SEED_FILES)
    assert "decisions.json" not in seed.SECURITY_FILES


def test_clm_1901_is_in_the_queue_and_in_neither_evaluation_set(client):
    queued = {claim["claim_id"] for claim in client.get("/api/claims").json()}
    assert "CLM-1901" in queued
    for evaluation_set in ("evaluation", "held_out"):
        made = client.post(
            "/api/runs/evaluations",
            json={"evaluation_set": evaluation_set, "tiny": False, "agents": 3},
        )
        copied = {copy["claim_id"] for copy in made.json()["claims"]}
        assert not any(copy.startswith("CLM-1901") for copy in copied)
        assert len(copied) == 25
    with db.engine().connect() as conn:
        originals = evaluations.originals(conn, "evaluation")
    assert len(originals) == 25
    assert "CLM-1901" not in {record["claim_id"] for record in originals}


def test_seeds_only_once(client):
    client.get("/api/claims")
    set_status("decided", "CLM-1001")
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert count_claims() == QUEUE


def test_reset(client):
    client.get("/api/claims")
    set_status("decided")
    seed.reset()
    assert {c["status"] for c in client.get("/api/claims").json()} == {"waiting"}


def test_reset_says_where():
    assert db.where(db.engine()).endswith("undercover.db")


def test_a_database_with_no_claims_is_seeded_again(client):
    client.get("/api/claims")
    with db.engine().begin() as conn:
        conn.execute(delete(db.claims))
    seed.ready.cache_clear()
    assert len(client.get("/api/claims").json()) == QUEUE


def test_seeding_drops_the_tables_earlier_builds_made(client):
    client.get("/api/claims")
    with db.engine().begin() as conn:
        Table("usage", MetaData(), Column("usage_id", Integer)).create(conn)
    seed.reset()
    with db.engine().connect() as conn:
        assert not inspect(conn).has_table("usage")


def test_seeding_stores_the_answer_key_apart(tmp_path):
    assert seed.reset() == "25 held-out claims and 50 handlers' decisions"
    with db.engine().connect() as conn:
        held_out = conn.execute(select(func.count()).select_from(db.held_out_claims))
        assert held_out.scalar_one() == 25
        tiny = select(func.count()).where(db.handler_decisions.c.tiny)
        assert conn.execute(tiny).scalar_one() == 10
    assert count_claims() == QUEUE


def test_seeding_makes_version_1_and_the_models_allowed(client):
    configuration = client.get("/api/configuration").json()
    assert configuration["current"] == 1
    assert len(configuration["versions"]) == 1
    luna, *others = configuration["models_allowed"]
    assert (luna["model"], luna["reasoning_efforts"], luna["input_price"]) == (
        "openai/gpt-6-luna",
        ["none", "low", "medium"],
        0.1,
    )
    assert len(others) == 2


@pytest.mark.parametrize("spec", ["anthropic:claude-haiku-5-5", "openrouter"])
def test_a_model_name_that_isnt_a_free_model_is_refused(monkeypatch, spec):
    monkeypatch.setenv("MODEL_NAME", spec)
    with pytest.raises(ValueError, match="a free model is openrouter:model"):
        seed.reset()


def test_on_a_free_model_it_is_version_1_and_the_only_model_allowed(
    client, monkeypatch
):
    monkeypatch.setenv("MODEL_NAME", "openrouter:openrouter/free")
    seed.reset()
    current = client.get("/api/versions/current").json()
    assert (current["model"], current["reasoning_effort"], current["provider"]) == (
        "openrouter/free",
        "default",
        "openrouter",
    )
    assert current["options"] == {}
    [free] = client.get("/api/configuration").json()["models_allowed"]
    assert (free["model"], free["input_price"], free["output_price"]) == (
        "openrouter/free",
        0,
        0,
    )
