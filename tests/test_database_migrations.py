from sqlalchemy import create_engine, text

from reprove.database import Database


def test_sqlite_upgrade_adds_retention_column_without_dropping_artifacts(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE artifacts (id VARCHAR(36) PRIMARY KEY, run_id VARCHAR(36), kind VARCHAR(80), uri TEXT, content_type VARCHAR(100), size_bytes INTEGER, redacted BOOLEAN, created_at DATETIME)"))
        connection.execute(text("INSERT INTO artifacts (id, run_id, kind, uri, content_type, size_bytes, redacted) VALUES ('a', 'r', 'evidence_bundle', 'evidence.json', 'application/json', 1, 1)"))
    Database(url).create_all()
    with engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(artifacts)"))}
        assert "expires_at" in columns
        assert connection.execute(text("SELECT count(*) FROM artifacts")).scalar() == 1
