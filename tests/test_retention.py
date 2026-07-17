from datetime import timedelta

from reprove.database import ArtifactRecord, Database, utcnow
from reprove.store import RunStore


def test_expired_artifact_is_removed_from_store_and_disk(tmp_path):
    database = Database("sqlite://")
    database.create_all()
    store = RunStore(database, tmp_path / "artifacts")
    path = tmp_path / "expired.json"; path.write_text("{}")
    with database.session() as session:
        org = store.ensure_organization("acme")
        repo = store.ensure_repository("acme", "acme/demo")
        run = store.create_run(repo.id, kind="issue_prover", claim="claim")
        session.add(ArtifactRecord(run_id=run.id, kind="evidence_bundle", uri=str(path), expires_at=utcnow() - timedelta(seconds=1)))
        session.commit()
    assert store.purge_expired_artifacts() == 1
    assert not path.exists()
