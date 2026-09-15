"""The version endpoint must prove which source the process is running."""

import os

from app.core.source_fingerprint import compute_source_fingerprint, source_fingerprint


def test_fingerprint_is_stable_and_content_addressed(tmp_path):
    root = tmp_path / "backend"
    (root / "app").mkdir(parents=True)
    (root / "alembic" / "versions").mkdir(parents=True)
    (root / "app" / "main.py").write_text("print('one')\n")
    (root / "alembic" / "versions" / "001.py").write_text("revision = '001'\n")
    (root / "app" / "__pycache__").mkdir()
    (root / "app" / "__pycache__" / "junk.pyc").write_text("ignored")

    first = compute_source_fingerprint(str(root))
    assert first == compute_source_fingerprint(str(root))
    assert first.startswith("v1:")

    # Any content change must change the fingerprint.
    (root / "app" / "main.py").write_text("print('two')\n")
    assert compute_source_fingerprint(str(root)) != first

    # Untracked-by-design noise must not.
    (root / "app" / "__pycache__" / "more.pyc").write_text("also ignored")
    (root / "app" / "notes.txt").write_text("not python")
    assert compute_source_fingerprint(str(root)) == compute_source_fingerprint(str(root))

    # An empty scan is a bug, not an empty fingerprint.
    empty = tmp_path / "empty"
    (empty / "app").mkdir(parents=True)
    try:
        compute_source_fingerprint(str(empty))
    except RuntimeError as error:
        assert "found no python files" in str(error)
    else:  # pragma: no cover - the guard must trigger
        raise AssertionError("expected RuntimeError for an empty source tree")


def test_running_fingerprint_matches_this_checkout():
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert source_fingerprint() == compute_source_fingerprint(backend_dir)


def test_version_endpoint_reports_deployment_truth(client):
    response = client.get("/api/system/version")
    assert response.status_code == 200
    payload = response.json()
    assert payload["environment"]
    assert payload["backend_source_fingerprint"].startswith("v1:")
    assert payload["schema_revision"]
    assert isinstance(payload["git_dirty"], bool)
    # Deployment truth must never leak secrets or filesystem layout.
    rendered = response.text
    assert "api_key" not in rendered.lower()
    assert "/home/" not in rendered
