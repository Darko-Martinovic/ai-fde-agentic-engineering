import shutil

from sqlalchemy import delete

from backend import db, seed
from backend.tests.direct_changes import count_claims, set_status


def test_seeds_from_the_seed_files_alone(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for name in seed.SEED_FILES:
        shutil.copy(seed.DATA_DIR / name, data / name)
    monkeypatch.setattr(seed, "DATA_DIR", data)
    seed.reset()
    assert count_claims() == 25


def test_seed_files_leave_out_the_answer_key():
    assert not any("evals" in name or "security" in name for name in seed.SEED_FILES)


def test_seeds_only_once(client):
    client.get("/api/claims")
    set_status("decided", "CLM-1001")
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert count_claims() == 25


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
    assert len(client.get("/api/claims").json()) == 25
