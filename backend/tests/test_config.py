from backend import config
from backend.__main__ import main


def test_database_path_is_relative_to_the_repo(monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", "backend/undercover.db")
    assert config.database_path() == config.ROOT / "backend" / "undercover.db"


def test_database_path_can_be_absolute(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "x.db"))
    assert config.database_path() == tmp_path / "x.db"


def test_the_backend_runs_where_the_settings_say(monkeypatch):
    started = {}
    monkeypatch.setattr("uvicorn.run", lambda app, **options: started.update(options))
    monkeypatch.setenv("BACKEND_PORT", "9123")
    monkeypatch.setenv("BACKEND_RELOAD", "false")
    main()
    assert started["port"] == 9123
    assert started["reload"] is False
