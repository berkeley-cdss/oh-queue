"""Signing in with bCourses, roles in each course, and the development login."""

from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from authlib.integrations.base_client import OAuthError

from oh_queue import canvas_service
from oh_queue.login import _safe_next
from oh_queue.models import MAX_OFFERING_CANVAS_ID, Account, ConfigEntry, User, db
from tests.conftest import AUTHORIZE, COURSE, canvas_sign_in, log_in, role


def current_user(client):
    """Who the course's queue says is signed in, as the page loads it."""
    assert client.get(COURSE + "/").status_code == 200
    response = client.post(COURSE + "/api/connect", json={"url": "http://localhost/"})
    assert response.status_code == 200
    states = [state for _, state in response.get_json()["updates"] if "current_user" in state]
    return states[0]["current_user"]


@pytest.mark.parametrize("roles", [role(is_staff=True), role(is_staff=True, is_admin=True)])
def test_staff_in_the_course_are_staff(client, roles):
    canvas_sign_in(client, "ta@example.edu", {"101": roles})
    user = current_user(client)
    assert user["isStaff"]
    assert user["name"] == "Ta"
    with client.application.app_context():
        assert User.query.filter_by(email="ta@example.edu").one().course == "cs61a"


def test_students_and_staff_of_other_courses_are_not_staff(client):
    canvas_sign_in(client, "student@example.edu", {"101": role(is_student=True), "202": role(is_staff=True)})
    assert not current_user(client)["isStaff"]


def test_roles_are_updated_at_each_sign_in(client):
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_staff=True)})
    assert current_user(client)["isStaff"]
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_student=True)})
    assert not current_user(client)["isStaff"]
    with client.application.app_context():
        assert User.query.filter_by(email="ta@example.edu").count() == 1
        assert Account.query.count() == 1


def test_admin_override_members_are_staff_in_every_course(client):
    canvas_sign_in(client, "admin@example.edu", {"999": role(is_student=True)})
    assert current_user(client)["isStaff"]
    with client.application.app_context():
        assert Account.query.one().is_global_admin


def test_signing_in_keeps_each_course_s_existing_users(client):
    with client.application.app_context():
        db.session.add(User(email="ta@example.edu", name="Old Name", is_staff=False, course="cs61a",
                            call_url="meet.google.com/ta"))
        db.session.commit()
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_staff=True)})
    current_user(client)
    with client.application.app_context():
        user = User.query.one()
        assert (user.name, user.is_staff, user.call_url) == ("Ta", True, "meet.google.com/ta")


def test_people_off_the_roster_are_students_unless_the_course_refuses_them(client):
    canvas_sign_in(client, "visitor@example.edu", {})
    # The first visit sets up the course's settings.
    assert client.get(COURSE + "/").status_code == 200
    user = current_user(client)
    assert user is not None and not user["isStaff"]

    with client.application.app_context():
        entry = ConfigEntry.query.filter_by(key="only_registered_students", course="cs61a").one()
        entry.value = "true"
        db.session.commit()
    response = client.get(COURSE + "/")
    assert response.status_code == 403
    assert b"roster" in response.data

    canvas_sign_in(client, "visitor@example.edu", {"101": role(is_student=True)})
    assert client.get(COURSE + "/").status_code == 200


def test_cookies_from_the_per_course_sites_are_ignored(client):
    with client.application.app_context():
        db.session.add(User(email="ta@example.edu", name="TA", is_staff=True, course="cs61a"))
        db.session.commit()
    client.get(COURSE + "/")
    # Flask-Login's session key, holding a User id as the per-course sites did.
    with client.session_transaction() as session:
        session["_user_id"] = "1"
    assert current_user(client) is None


class CanvasCourse(SimpleNamespace):
    pass


def test_user_courses_have_each_role_and_skip_courses_that_cant_be_offerings(app_context):
    def course(id, *types, role=None):
        return CanvasCourse(id=id, name=f"Course {id}", course_code=f"C{id}", term={"start_at": "2026-08-19"},
                            enrollments=[{"type": t, "role": role or t} for t in types])
    courses = [
        course(1, "teacher"),
        course(2, "ta", role="Lead TA"),
        course(3, "ta"),
        course(4, "student"),
        course(5, "observer"),
        course(MAX_OFFERING_CANVAS_ID + 1, "student"),
        CanvasCourse(id=7, name="No access"),
    ]
    with patch.object(canvas_service, "_client") as client:
        client.return_value.get_user.return_value.get_courses.return_value = courses
        result = canvas_service.get_user_courses(42, "token")
    roles = {i: (c["is_staff"], c["is_admin"], c["is_student"]) for i, c in result.items()}
    assert roles == {
        "1": (True, True, False),
        "2": (True, True, False),
        "3": (True, False, False),
        "4": (False, False, True),
        "5": (False, False, False),
    }
    assert result["1"]["start_at"] == "2026-08-19"


def test_login_redirects_to_canvas(client):
    response = client.get(f"/login/?next={COURSE}/admin", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 302
    location = urlparse(response.headers["Location"])
    query = parse_qs(location.query)
    assert (location.netloc, location.path) == ("canvas.example.edu", "/login/oauth2/auth")
    assert query["client_id"] == ["client-id"]
    # Behind Cloud Run's proxy, the callback is https.
    assert query["redirect_uri"] == ["https://localhost/authorized/"]
    assert set(query["scope"][0].split()) == set(canvas_service.SCOPES)
    with client.session_transaction() as s:
        assert s["after_login"] == f"{COURSE}/admin"


def test_login_without_a_client_id(client, monkeypatch):
    monkeypatch.setitem(client.application.config, "CANVAS_CLIENT_ID", None)
    response = client.get("/login/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/testing-login/")
    monkeypatch.setitem(client.application.config, "ENV", "prod")
    assert client.get("/login/").status_code == 503


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


def test_sign_in_goes_back_to_the_page_or_to_the_offerings(client):
    client.get(f"/login/?next={COURSE}/admin")
    response = canvas_sign_in(client, "ta@example.edu", {})
    assert response.headers["Location"].endswith(f"{COURSE}/admin")
    response = canvas_sign_in(client, "ta@example.edu", {})
    assert response.headers["Location"].endswith("/offerings")


def test_canvas_errors_are_escaped(client):
    error = OAuthError(error="access_denied", description="<script>alert(1)</script>")
    with patch(AUTHORIZE, side_effect=error):
        response = client.get("/authorized/")
    assert response.status_code == 403
    assert b"<script>" not in response.data
    assert b"&lt;script&gt;" in response.data


def test_development_login(client):
    log_in(client, "ta@example.edu", is_staff=True)
    assert current_user(client)["isStaff"]
    with client.application.app_context():
        assert User.query.filter_by(email="ta@example.edu", course="cs61a").one().is_staff


def test_no_development_login_in_production(client, monkeypatch):
    monkeypatch.setitem(client.application.config, "ENV", "prod")
    assert client.get("/testing-login/").status_code == 404
    response = client.post("/testing-login/authorized", data={"email": "a@example.edu", "name": "A"})
    assert response.status_code == 404
    with client.application.app_context():
        assert Account.query.count() == 0


def test_logout(client):
    log_in(client)
    assert current_user(client) is not None
    # Only a POST signs out, so other sites can't.
    assert client.get("/logout/").status_code == 405
    assert current_user(client) is not None
    response = client.post("/logout/")
    assert response.status_code == 302
    assert current_user(client) is None
