"""Signing in with bCourses, and the development login."""

from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from authlib.integrations.base_client import OAuthError
from flask import session
from flask_login import current_user

from oh_queue import canvas_service
from oh_queue.login import _safe_next, complete_login
from oh_queue.models import User
from tests.conftest import log_in


class Enrollment:
    def __init__(self, type, role=None):
        self.type = type
        self.role = role or type


class CanvasCourse:
    def __init__(self, *enrollment_types):
        self.enrollment_types = enrollment_types

    def get_enrollments(self, user_id):
        return [Enrollment(t) for t in self.enrollment_types]


def sign_in(app, email, *enrollment_types, override=False):
    """Run complete_login for Canvas user 42 with Canvas mocked; return the
    signed-in User and the mocked get_course."""
    profile = {"primary_email": email, "name": email.split("@")[0].title()}
    with app.test_request_context("/"), \
         patch.object(canvas_service, "get_profile", return_value=profile), \
         patch.object(canvas_service, "get_course", return_value=CanvasCourse(*enrollment_types)) as get_course, \
         patch.object(canvas_service, "in_admin_override_course", return_value=override):
        complete_login({"user": {"id": 42}, "access_token": "token"})
        assert current_user.email == email
        # Nothing after sign-in uses the Canvas token, so it isn't kept.
        assert "token" not in [v for v in session.values() if isinstance(v, str)]
    with app.app_context():
        return User.query.filter_by(email=email).one(), get_course


@pytest.mark.parametrize("enrollment", ["TaEnrollment", "TeacherEnrollment"])
def test_tas_and_teachers_are_staff(app, enrollment):
    user, get_course = sign_in(app, "ta@example.edu", enrollment)
    assert user.is_staff
    assert user.course == "cs61a"
    assert user.name == "Ta"
    # Roles come from the configured bCourses course.
    get_course.assert_called_once_with(101, "token")


@pytest.mark.parametrize("enrollments", [("StudentEnrollment",), ("ObserverEnrollment",), ()])
def test_others_are_not_staff(app, enrollments):
    user, _ = sign_in(app, "student@example.edu", *enrollments)
    assert not user.is_staff


def test_role_is_updated_at_each_sign_in(app):
    sign_in(app, "ta@example.edu", "TaEnrollment")
    user, _ = sign_in(app, "ta@example.edu", "StudentEnrollment")
    assert not user.is_staff
    with app.app_context():
        assert User.query.filter_by(email="ta@example.edu").count() == 1


def test_admin_override_members_are_staff_without_reading_the_course(app):
    user, get_course = sign_in(app, "admin@example.edu", override=True)
    assert user.is_staff
    get_course.assert_not_called()


class Course:
    def __init__(self, id):
        self.id = id


def test_admin_override_course_is_the_configured_one(app_context):
    with patch.object(canvas_service, "_client") as client:
        courses = client.return_value.get_user.return_value.get_courses
        courses.return_value = [Course(1), Course(999)]
        assert canvas_service.in_admin_override_course(42, "token")
        courses.return_value = [Course(1), Course(1549197)]
        assert not canvas_service.in_admin_override_course(42, "token")


def test_no_admin_override_course_skips_canvas(app_context, monkeypatch):
    monkeypatch.setitem(app_context.config, "ADMIN_OVERRIDE_CANVAS_COURSE_ID", None)
    with patch.object(canvas_service, "_client") as client:
        assert not canvas_service.in_admin_override_course(42, "token")
    client.assert_not_called()


def test_canvas_login_redirects_to_canvas(client):
    response = client.get("/oauth/canvas_login?next=/admin", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 302
    location = urlparse(response.headers["Location"])
    query = parse_qs(location.query)
    assert (location.netloc, location.path) == ("canvas.example.edu", "/login/oauth2/auth")
    assert query["client_id"] == ["client-id"]
    # Behind Cloud Run's proxy, the callback is https.
    assert query["redirect_uri"] == ["https://localhost/oauth/canvas_authorized"]
    assert set(query["scope"][0].split()) == set(canvas_service.SCOPES)
    with client.session_transaction() as s:
        assert s["after_login"] == "/admin"


def test_canvas_login_without_a_client_id(client, monkeypatch):
    monkeypatch.setitem(client.application.config, "CANVAS_CLIENT_ID", None)
    assert client.get("/oauth/canvas_login").status_code == 503


@pytest.mark.parametrize("target, expected", [
    ("/admin", "/admin"),
    ("/tickets/3/?a=b", "/tickets/3/?a=b"),
    (None, None),
    ("", None),
    ("https://evil.example.edu/", None),
    ("//evil.example.edu/", None),
    ("/\\evil.example.edu/", None),
    ("/\t/evil.example.edu/", None),
])
def test_only_paths_on_this_site_are_followed_after_sign_in(target, expected):
    assert _safe_next(target) == expected


def test_canvas_authorized_signs_in_and_goes_back(client):
    with client.session_transaction() as s:
        s["after_login"] = "/admin"
    with patch("authlib.integrations.flask_client.FlaskOAuth2App.authorize_access_token",
               return_value={"user": {"id": 42}, "access_token": "token"}), \
         patch("oh_queue.login.complete_login") as complete:
        response = client.get("/oauth/canvas_authorized?code=abc&state=xyz")
    complete.assert_called_once_with({"user": {"id": 42}, "access_token": "token"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/admin")


def test_canvas_errors_are_escaped(client):
    error = OAuthError(error="access_denied", description="<script>alert(1)</script>")
    with patch("authlib.integrations.flask_client.FlaskOAuth2App.authorize_access_token", side_effect=error):
        response = client.get("/oauth/canvas_authorized")
    assert response.status_code == 403
    assert b"<script>" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_development_login(client):
    log_in(client, "ta@example.edu", is_staff=True)
    with client.application.app_context():
        assert User.query.filter_by(email="ta@example.edu", course="cs61a").one().is_staff


def test_no_development_login_in_production(client, monkeypatch):
    monkeypatch.setitem(client.application.config, "ENV", "prod")
    assert client.get("/testing-login/").status_code == 404
    response = client.post("/testing-login/authorized", data={"email": "a@example.edu", "name": "A"})
    assert response.status_code == 404
    with client.application.app_context():
        assert User.query.count() == 0


def test_logout(client):
    def can_change_settings():
        response = client.post("/api/update_config", json={"key": "is_queue_open", "value": "true"})
        return "messages" not in (response.get_json()["action"] or {})

    client.get("/")
    log_in(client)
    assert can_change_settings()
    client.get("/oauth/logout")
    assert not can_change_settings()
