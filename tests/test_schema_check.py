"""The check that refuses requests while the database doesn't match the
migrations, as on a PR preview whose PR adds a migration."""

from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.script import ScriptDirectory

from oh_queue import MIGRATIONS_DIR
from oh_queue import schema_check
from oh_queue.models import db
from tests.conftest import COURSE

HEAD = ScriptDirectory(MIGRATIONS_DIR).get_current_head()


@pytest.fixture()
def checked_app(app, monkeypatch):
    """The app with the check on (conftest turns it off), and nothing cached."""
    monkeypatch.setitem(app.config, "CHECK_SCHEMA", True)
    monkeypatch.delenv("PREVIEW_PR", raising=False)
    app.extensions["schema_check"].update(expires_at=None, problem=None)
    yield app
    with app.app_context(), db.engine.begin() as conn:
        # Not one of the app's tables, so the app fixture doesn't drop it.
        conn.execute(sa.text("DROP TABLE IF EXISTS alembic_version"))


def stamp(app, revision):
    with app.app_context(), db.engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(sa.text("DELETE FROM alembic_version"))
        conn.execute(sa.text("INSERT INTO alembic_version VALUES (:r)"), {"r": revision})


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.text == "ok"


def test_matching_database_is_served(checked_app):
    stamp(checked_app, HEAD)
    client = checked_app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200


def test_database_behind_says_to_upgrade(checked_app):
    # create_all made the tables, but no migration is recorded.
    client = checked_app.test_client()
    response = client.get("/health")
    assert response.status_code == 503
    assert f"expects {HEAD}" in response.text
    assert "flask db upgrade" in response.text

    page = client.get("/")
    assert page.status_code == 503
    assert "Database migration needed" in page.text

    api = client.post(COURSE + "/api/connect", json={})
    assert api.status_code == 503
    assert "flask db upgrade" in api.json["message"]


def test_static_files_are_served(checked_app):
    # The error page's stylesheets.
    response = checked_app.test_client().get("/static/pages/css/style.css")
    assert response.status_code == 200


def test_preview_with_a_migration_says_to_merge(checked_app, monkeypatch):
    monkeypatch.setenv("PREVIEW_PR", "42")
    response = checked_app.test_client().get("/")
    assert response.status_code == 503
    assert "This is a preview of PR #42, which adds a database migration" in response.text


def test_preview_older_than_database_says_to_merge_main(checked_app, monkeypatch):
    monkeypatch.setenv("PREVIEW_PR", "42")
    stamp(checked_app, "0123456789ab")
    response = checked_app.test_client().get("/health")
    assert response.status_code == 503
    assert "whose branch is older than the staging database (at migration 0123456789ab)" in response.text
    assert "Merge main into the PR's branch" in response.text


def test_result_is_cached(checked_app):
    client = checked_app.test_client()
    assert client.get("/health").status_code == 503
    stamp(checked_app, HEAD)
    # Still the cached result, until it's a minute old.
    assert client.get("/health").status_code == 503
    checked_app.extensions["schema_check"]["expires_at"] = None
    assert client.get("/health").status_code == 200


def test_course_pages_are_refused_before_loading_the_offering(checked_app):
    # As on a preview whose PR adds a column to offerings: loading the course
    # would fail on the missing column, so the check has to come first.
    with checked_app.app_context(), db.engine.begin() as conn:
        conn.execute(sa.text("ALTER TABLE offerings RENAME TO offerings_old"))
    try:
        client = checked_app.test_client()
        page = client.get(COURSE + "/")
        assert page.status_code == 503
        assert "Database migration needed" in page.text

        api = client.post(COURSE + "/api/connect", json={})
        assert api.status_code == 503
        assert api.is_json
        assert "flask db upgrade" in api.json["message"]
    finally:
        with checked_app.app_context(), db.engine.begin() as conn:
            conn.execute(sa.text("ALTER TABLE offerings_old RENAME TO offerings"))


def test_database_ahead_is_served_outside_previews(checked_app, caplog):
    # The old version while a deploy's new version migrates: keep serving.
    stamp(checked_app, "0123456789ab")
    client = checked_app.test_client()
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert "at migration 0123456789ab, which this version doesn't have" in caplog.text


def test_failed_check_is_retried_after_a_while(checked_app, monkeypatch):
    stamp(checked_app, HEAD)
    client = checked_app.test_client()
    with patch.object(schema_check, "schema_problem", side_effect=RuntimeError("unreachable")) as check:
        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
        # Not tried again on every request.
        assert check.call_count == 1

        now = schema_check.time.monotonic()
        monkeypatch.setattr(schema_check.time, "monotonic", lambda: now + schema_check.FAILURE_SECONDS + 1)
        assert client.get("/health").status_code == 200
        assert check.call_count == 2
