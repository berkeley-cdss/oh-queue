"""pytest fixtures, as in seating and sections.

The app is built when oh_queue is imported, from settings read by config.py,
so the test settings are put in the environment before that import. Each test
gets empty tables, except for one offering: CS 61A, Canvas course 101, stored
under the key the per-course sites used.
"""

import os
import tempfile
from unittest.mock import patch

_db_dir = tempfile.mkdtemp()
TEST_ENV = {
    "ENV": "dev",
    "SECRET_KEY": "test",
    "DATABASE_URL": "sqlite:///" + os.path.join(_db_dir, "test.db"),
    "CANVAS_SERVER_URL": "https://canvas.example.edu/",
    "CANVAS_CLIENT_ID": "client-id",
    "CANVAS_CLIENT_SECRET": "client-secret",
    "ADMIN_OVERRIDE_CANVAS_COURSE_ID": "999",
}
os.environ.update(TEST_ENV)

import pytest  # noqa: E402
from flask_migrate import Migrate  # noqa: E402

from oh_queue import app as flask_app  # noqa: E402
from oh_queue import canvas_service  # noqa: E402
from oh_queue.models import Offering  # noqa: E402
from oh_queue.models import db as sqlalchemy_db  # noqa: E402

# The test offering's pages and API.
COURSE = "/offerings/101"

# manage.py registers Flask-Migrate for the CLI; the migration tests need it too.
# The tests build their tables with create_all, so the database has no
# migration for the schema check to compare; test_schema_check turns it on.
flask_app.config["CHECK_SCHEMA"] = False

if "migrate" not in flask_app.extensions:
    Migrate(flask_app, sqlalchemy_db)


@pytest.fixture()
def app():
    # The app context isn't kept open during the test: requests would share it,
    # and with it Flask-Login's signed-in user in g. Tests that need one open
    # their own.
    with flask_app.app_context():
        sqlalchemy_db.drop_all()
        sqlalchemy_db.create_all()
        sqlalchemy_db.session.add(Offering(canvas_id=101, key="cs61a", name="COMPSCI 61A - LEC 001", code="CS 61A"))
        sqlalchemy_db.session.commit()
    yield flask_app
    with flask_app.app_context():
        sqlalchemy_db.session.remove()
        sqlalchemy_db.drop_all()


@pytest.fixture()
def app_context(app):
    """For tests that call the app's code directly, not through requests."""
    with app.app_context():
        yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def log_in(client, email="staff@example.edu", name="Staff", is_staff=True):
    """Sign in through the development login, as a TA or a student in every
    offering, then open the test offering, which makes its User row."""
    form = {"email": email, "name": name}
    if is_staff:
        form["is_staff"] = "on"
    response = client.post("/testing-login/authorized", data=form)
    assert response.status_code == 302
    assert client.get(COURSE + "/").status_code == 200
    return response


AUTHORIZE = "authlib.integrations.flask_client.FlaskOAuth2App.authorize_access_token"


def role(is_staff=False, is_student=False, is_admin=False,
         name="COMPSCI 61A - LEC 001", code="COMPSCI 61A", start_at="2026-08-19T07:00:00Z"):
    """An entry of get_user_courses."""
    return {"name": name, "code": code, "start_at": start_at,
            "is_staff": is_staff, "is_admin": is_admin, "is_student": is_student}


def canvas_sign_in(client, email, courses, canvas_user_id=42):
    """Sign in through /authorized/ as Canvas user ``canvas_user_id``, enrolled in
    ``courses`` ({str(canvas course id): role(...)}), with Canvas mocked."""
    profile = {"primary_email": email, "name": email.split("@")[0].title()}
    with patch(AUTHORIZE, return_value={"user": {"id": canvas_user_id}, "access_token": "token"}), \
         patch.object(canvas_service, "get_profile", return_value=profile), \
         patch.object(canvas_service, "get_user_courses", return_value=courses) as get_user_courses:
        response = client.get("/authorized/?code=abc&state=xyz")
    assert response.status_code == 302
    get_user_courses.assert_called_once_with(str(canvas_user_id), "token")
    return response
