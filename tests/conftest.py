"""pytest fixtures, as in seating and sections.

The app is built when oh_queue is imported, from settings read by config.py,
so the test settings are put in the environment before that import. Each test
gets empty tables.
"""

import os
import tempfile

_db_dir = tempfile.mkdtemp()
TEST_ENV = {
    "ENV": "dev",
    "SECRET_KEY": "test",
    "DATABASE_URL": "sqlite:///" + os.path.join(_db_dir, "test.db"),
    "COURSE_KEY": "cs61a",
    "CANVAS_COURSE_ID": "101",
    "CANVAS_SERVER_URL": "https://canvas.example.edu/",
    "CANVAS_CLIENT_ID": "client-id",
    "CANVAS_CLIENT_SECRET": "client-secret",
    "ADMIN_OVERRIDE_CANVAS_COURSE_ID": "999",
}
os.environ.update(TEST_ENV)
# Settings a developer's shell might have that the tests mustn't use.
for name in ("LLM_TIPS_ENDPOINT", "LLM_TIPS_AUTH_TOKEN"):
    os.environ.pop(name, None)

import pytest  # noqa: E402
from flask_migrate import Migrate  # noqa: E402

from oh_queue import app as flask_app  # noqa: E402
from oh_queue.models import db as sqlalchemy_db  # noqa: E402

# manage.py registers Flask-Migrate for the CLI; the migration tests need it too.
if "migrate" not in flask_app.extensions:
    Migrate(flask_app, sqlalchemy_db)


@pytest.fixture()
def app():
    with flask_app.app_context():
        sqlalchemy_db.drop_all()
        sqlalchemy_db.create_all()
        yield flask_app
        sqlalchemy_db.session.remove()
        sqlalchemy_db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def log_in(client, email="staff@example.edu", name="Staff", is_staff=True):
    """Sign in through the development login."""
    form = {"email": email, "name": name}
    if is_staff:
        form["is_staff"] = "on"
    response = client.post("/testing-login/authorized", data=form)
    assert response.status_code == 302
    return response
