import shutil

from backend import db, seed


def count_claims() -> int:
    conn = db.connect()
    total = conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
    conn.close()
    return total


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
    conn = db.connect()
    with conn:
        conn.execute("UPDATE claims SET status = 'decided' WHERE claim_id = 'CLM-1001'")
    conn.close()
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert count_claims() == 25


def test_reset(client):
    client.get("/api/claims")
    conn = db.connect()
    with conn:
        conn.execute("UPDATE claims SET status = 'decided'")
    conn.close()
    seed.reset()
    assert {c["status"] for c in client.get("/api/claims").json()} == {"waiting"}
