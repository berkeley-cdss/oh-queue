"""Signing in with bCourses, roles in each course. The dev login is in test_dev_login.py."""

from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from authlib.integrations.base_client import OAuthError

from oh_queue import canvas_service
from oh_queue.login import _safe_next
from oh_queue.models import MAX_OFFERING_CANVAS_ID, ChatMessage, Heartbeat, Ticket, TicketStatus, User, db, utcnow
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
        assert User.query.filter_by(email="ta@example.edu").one().staff_offerings == {"cs61a"}


def test_students_and_staff_of_other_courses_are_not_staff(client):
    canvas_sign_in(client, "student@example.edu", {"101": role(is_student=True), "202": role(is_staff=True)})
    assert not current_user(client)["isStaff"]


def test_roles_are_updated_at_each_sign_in(client):
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_staff=True)})
    assert current_user(client)["isStaff"]
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_student=True)})
    assert not current_user(client)["isStaff"]
    with client.application.app_context():
        user = User.query.one()
        assert (user.staff_offerings, user.student_offerings) == (set(), {"cs61a"})


def test_admin_override_members_are_staff_in_every_course(client):
    canvas_sign_in(client, "admin@example.edu", {"999": role(is_student=True)})
    assert current_user(client)["isStaff"]
    with client.application.app_context():
        assert User.query.one().is_global_admin


def moved_user(email, *, staff_in=(), student_in=(), **fields):
    """Someone moved from the per-course sites, who hasn't signed in since."""
    user = User(email=email, name="Old Name", **fields)
    for key in staff_in:
        user.set_role(key, is_staff=True)
    for key in student_in:
        user.set_role(key, is_staff=False)
    db.session.add(user)
    db.session.commit()
    return user.id


def test_first_sign_in_claims_the_moved_user_with_that_email(client):
    with client.application.app_context():
        user_id = moved_user("TA@example.edu", student_in=["cs61a", "data8"], call_url="meet.google.com/ta")
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_staff=True)}, canvas_user_id=77)
    current_user(client)
    with client.application.app_context():
        user = User.query.one()
        assert (user.id, user.canvas_id, user.name, user.call_url) == (user_id, "77", "Ta", "meet.google.com/ta")
        # Staff in the course now, and still a student in the old one.
        assert (user.staff_offerings, user.student_offerings) == ({"cs61a"}, {"data8"})


def test_sign_in_never_claims_someone_else_by_email(client):
    canvas_sign_in(client, "ta@example.edu", {}, canvas_user_id=1)
    with patch(AUTHORIZE, return_value={"user": {"id": 99}, "access_token": "token"}), \
         patch.object(canvas_service, "get_profile", return_value={"primary_email": "ta@example.edu"}), \
         patch.object(canvas_service, "get_user_courses", return_value={}):
        response = client.get("/authorized/?code=abc&state=xyz")
    assert response.status_code == 403
    with client.application.app_context():
        assert [(u.canvas_id, u.email) for u in User.query] == [("1", "ta@example.edu")]


def test_a_changed_email_follows_the_canvas_id(client):
    canvas_sign_in(client, "ta@example.edu", {}, canvas_user_id=1)
    canvas_sign_in(client, "ta.new@example.edu", {}, canvas_user_id=1)
    with client.application.app_context():
        assert [(u.canvas_id, u.email) for u in User.query] == [("1", "ta.new@example.edu")]


def test_a_changed_email_merges_the_moved_user_with_that_email(client):
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_staff=True)}, canvas_user_id=1)
    current_user(client)
    with client.application.app_context():
        ta = User.query.one()
        moved_id = moved_user("ta.new@example.edu", staff_in=["data8"], doc_url="docs.google.com/ta")
        ticket = Ticket(status=TicketStatus.pending, user_id=moved_id, helper_id=ta.id, assignment_id=1, location_id=1,
                        question="1", course="data8")
        db.session.add(ticket)
        db.session.flush()
        db.session.add(ChatMessage(user_id=moved_id, ticket_id=ticket.id, body="hi", course="data8"))
        db.session.add(Heartbeat(user_id=moved_id, course="data8", time=utcnow()))
        db.session.commit()
        ta_id = ta.id

    canvas_sign_in(client, "ta.new@example.edu", {"101": role(is_staff=True)}, canvas_user_id=1)
    with client.application.app_context():
        assert db.session.get(User, moved_id) is None
        ta = User.query.one()
        assert (ta.id, ta.email, ta.doc_url) == (ta_id, "ta.new@example.edu", "docs.google.com/ta")
        assert ta.staff_offerings == {"cs61a", "data8"}
        assert [(t.user_id, t.helper_id) for t in Ticket.query] == [(ta_id, ta_id)]
        assert [m.user_id for m in ChatMessage.query] == [ta_id]
        assert sorted((h.user_id, h.course) for h in Heartbeat.query) == [(ta_id, "cs61a"), (ta_id, "data8")]


def test_a_changed_email_owned_by_another_account_keeps_the_old_one(client):
    canvas_sign_in(client, "ta@example.edu", {}, canvas_user_id=1)
    canvas_sign_in(client, "other@example.edu", {}, canvas_user_id=2)
    canvas_sign_in(client, "other@example.edu", {}, canvas_user_id=1)
    with client.application.app_context():
        assert sorted((u.canvas_id, u.email) for u in User.query) == [
            ("1", "ta@example.edu"), ("2", "other@example.edu")]


def test_only_people_enrolled_in_the_course_can_open_it(client):
    canvas_sign_in(client, "visitor@example.edu", {"202": role(is_student=True), "101": role()})
    response = client.get(COURSE + "/")
    assert response.status_code == 403
    page = response.get_data(as_text=True)
    # The site's error page, with the reason and a way back, not Werkzeug's bare one.
    assert "You aren&#39;t enrolled in this course on bCourses" in page
    assert 'href="/"' in page and "Back to the Office Hours Queue" in page
    response = client.post(COURSE + "/api/connect", json={"url": "http://localhost/"})
    assert response.status_code == 403
    assert "enrolled" in response.get_json()["message"]

    canvas_sign_in(client, "visitor@example.edu", {"101": role(is_student=True)})
    assert client.get(COURSE + "/").status_code == 200
    with client.application.app_context():
        assert User.query.filter_by(email="visitor@example.edu").count() == 1


@pytest.mark.parametrize("session_id", ["1", "account-1"])
def test_cookies_from_before_this_table_are_ignored(client, session_id):
    with client.application.app_context():
        moved_user("ta@example.edu", staff_in=["cs61a"])
    client.get(COURSE + "/")
    # Flask-Login's session key, holding a User id as the per-course sites did,
    # or an account id as the site did before it had one user per person.
    with client.session_transaction() as session:
        session["_user_id"] = session_id
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


def test_logout(client):
    log_in(client)
    assert current_user(client) is not None
    # Only a POST signs out, so other sites can't.
    assert client.get("/logout/").status_code == 405
    assert current_user(client) is not None
    response = client.post("/logout/")
    assert response.status_code == 302
    assert current_user(client) is None


def test_a_profile_without_an_email_is_refused_clearly(client):
    with patch(AUTHORIZE, return_value={"user": {"id": 42}, "access_token": "token"}), \
         patch.object(canvas_service, "get_profile", return_value={"name": "No Email"}), \
         patch.object(canvas_service, "get_user_courses", return_value={}):
        response = client.get("/authorized/?code=abc&state=xyz")
    assert response.status_code == 403
    assert b"no email address" in response.data
    with client.application.app_context():
        assert User.query.count() == 0
