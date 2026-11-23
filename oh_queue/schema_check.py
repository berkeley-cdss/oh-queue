"""Refuse requests while the database's schema doesn't match the code's
migrations, with a message saying why, instead of failing on the first query
that uses a missing column. Copied from sections (server/schema_check.py).

The usual cause is a PR preview whose PR adds a migration: previews share the
staging database and never run migrations (see the Dockerfile), so the
migration only reaches that database once the PR is merged and staging deploys.

It runs before anything else in the request queries the database, except
Flask-Session, which loads the session from its table when the request starts:
a migration that changes flask_sessions still fails with a server error.
"""

import os
import time

import flask
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from flask import current_app, jsonify, request

from oh_queue.errors import error_page
from oh_queue.models import db

# How long to trust a result, so most requests don't query the database for it.
CACHE_SECONDS = 60
# How long to wait before trying again when the check itself fails (say the
# database is unreachable), so an outage doesn't repeat it on every request.
FAILURE_SECONDS = 10


def schema_problem(migrations_dir: str) -> str | None:
    """Why requests should be refused because the database doesn't match the
    code's migrations, or None if they can be served."""
    script = ScriptDirectory(migrations_dir)
    code_heads = set(script.get_heads())
    with db.engine.connect() as connection:
        db_heads = set(MigrationContext.configure(connection).get_current_heads())
    if db_heads == code_heads:
        return None

    known = {revision.revision for revision in script.walk_revisions()}
    pr = os.getenv("PREVIEW_PR")
    db_names = ", ".join(sorted(db_heads)) or "none"
    code_names = ", ".join(sorted(code_heads))
    if db_heads - known:
        # The database has a migration this code doesn't know about.
        if pr:
            return (f"This is a preview of PR #{pr}, whose branch is older than the staging database "
                    f"(at migration {db_names}). Merge main into the PR's branch to update the preview.")
        # Outside previews this is the old version still serving while a deploy's
        # new version migrates (the Dockerfile's RUN_MIGRATIONS), or after a new
        # version failed to start. Migrations usually leave the old code working,
        # so keep serving rather than take the site down.
        current_app.logger.warning(
            "The database is at migration %s, which this version doesn't have; serving anyway", db_names
        )
        return None
    if pr:
        return (f"This is a preview of PR #{pr}, which adds a database migration ({code_names}). "
                f"PR previews share the staging database and never run migrations, so this preview "
                f"can't run. Merge the PR to see its changes on staging.")
    return (f"The database is at migration {db_names}, but this version of the Office Hours Queue "
            f"expects {code_names}. Run `flask db upgrade`.")


def check_schema_before_requests(app: flask.Flask, migrations_dir: str):
    """Refuse requests while the schema doesn't match, unless CHECK_SCHEMA is
    off (the tests build their tables with create_all, not migrations)."""
    # On the app, so the tests can clear it.
    cached = app.extensions["schema_check"] = {"expires_at": None, "problem": None}

    def current_problem():
        now = time.monotonic()
        if cached["expires_at"] is None or now >= cached["expires_at"]:
            try:
                cached["problem"] = schema_problem(migrations_dir)
                cached["expires_at"] = now + CACHE_SECONDS
            except Exception:
                # Can't tell: let requests run and report their own errors, and
                # try again shortly rather than on every request.
                current_app.logger.exception("Couldn't compare the database schema with the migrations")
                cached["problem"] = None
                cached["expires_at"] = now + FAILURE_SECONDS
        return cached["problem"]

    # A URL value preprocessor on the app, not a before_request hook: Flask runs
    # the app's preprocessors first, then the blueprints' (such as the course
    # pages' offering lookup, which queries the database), then before_request
    # hooks. Raising a response here stops the request before any of the others.
    @app.url_value_preprocessor
    def refuse_mismatched_schema(endpoint, values):
        if not current_app.config.get("CHECK_SCHEMA", True) or endpoint == "static":
            return
        problem = current_problem()
        if problem is None:
            return
        if request.path == "/health":
            response = flask.make_response(problem, 503)
        # As errors.py answers the course API.
        elif "/api/" in request.path:
            response = flask.make_response(jsonify({"message": problem}), 503)
        else:
            response = flask.make_response(error_page("Database migration needed", problem, 503))
        flask.abort(response)
