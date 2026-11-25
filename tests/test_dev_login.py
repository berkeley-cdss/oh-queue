"""The fake Canvas and /dev_login/, as in sections' tests/unit/test_dev_login.py."""

import pytest

from oh_queue import canvas_service
from oh_queue.dev_login import mock_user_roster
from oh_queue.models import Offering, User, db

# Seeded users (oh_queue/fake_canvas_data): a TA, a student and a teacher in CS 169A.
YU_LONG, JIMMY_XU, OSKI = "123456", "234567", "567890"
CS169A = 1234567


@pytest.fixture()
def mock_canvas(app, monkeypatch):
    monkeypatch.setitem(app.config, "MOCK_CANVAS", True)
    return app


@pytest.fixture()
def offering(mock_canvas):
    """CS 169A, set up in the queue."""
    with mock_canvas.app_context():
        db.session.add(Offering(canvas_id=CS169A, key=str(CS169A), name="CS 169A", code="COMPSCI 169A"))
        db.session.commit()


def dev_login(client, user_id):
    return client.post("/dev_login/", data={"user_id": user_id})


def test_roster_lists_the_seeded_users_by_name():
    assert [user["name"] for user in mock_user_roster()] == \
        ["Jimmy Xu", "Lavender Angela", "Oski Bear", "Sharon Lovera", "Yu Long"]


def test_roster_shows_each_users_roles():
    yu_long = next(u for u in mock_user_roster() if u["name"] == "Yu Long")
    assert (yu_long["id"], yu_long["email"]) == (YU_LONG, "long_yu@berkeley.edu")
    roles = {course["name"]: course["roles"] for course in yu_long["courses"]}
    assert roles["Introduction to Software Engineering (Fall 2023)"] == ["ta"]
    assert roles["Computer Architecture (Fall 2022)"] == ["student"]


def test_fake_canvas_profile(mock_canvas):
    with mock_canvas.app_context():
        profile = canvas_service.get_profile(YU_LONG, "dev_access_token")
    assert (profile["primary_email"], profile["name"]) == ("long_yu@berkeley.edu", "Yu Long")


def test_fake_canvas_courses_and_roles(mock_canvas):
    with mock_canvas.app_context():
        assert canvas_service.get_user_courses(OSKI, "dev_access_token") == {str(CS169A): {
            "name": "Introduction to Software Engineering (Fall 2023)", "code": "COMPSCI 169A",
            "start_at": "2023-08-16T07:00:00Z", "is_staff": True, "is_admin": True, "is_student": False,
        }}
        courses = canvas_service.get_user_courses(YU_LONG, "dev_access_token")
    assert {c: (i["is_staff"], i["is_admin"], i["is_student"]) for c, i in courses.items()} == \
        {str(CS169A): (True, False, False), "4567890": (False, False, True)}


def test_production_never_uses_the_fake_canvas(mock_canvas, monkeypatch):
    monkeypatch.setitem(mock_canvas.config, "ENV", "prod")
    with mock_canvas.app_context():
        assert not canvas_service.is_mock_canvas()


def test_login_goes_to_the_dev_login_page_and_back(client, offering):
    response = client.get(f"/login/?next=/offerings/{CS169A}/")
    assert response.headers["Location"].endswith("/dev_login/")
    page = client.get("/dev_login/").get_data(as_text=True)
    assert page.count('name="user_id" value=') == 5
    assert 'aria-label="Log in as Lavender Angela"' in page

    response = dev_login(client, YU_LONG)
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/offerings/{CS169A}/")
    with client.application.app_context():
        user = User.query.filter_by(canvas_id=YU_LONG).one()
        assert (user.email, user.name) == ("long_yu@berkeley.edu", "Yu Long")
        assert set(user.canvas_courses) == {str(CS169A), "4567890"}


@pytest.mark.parametrize("user_id, is_staff", [(YU_LONG, True), (OSKI, True), (JIMMY_XU, False)])
def test_seeded_users_get_their_role_in_the_course(client, offering, user_id, is_staff):
    dev_login(client, user_id)
    assert client.get(f"/offerings/{CS169A}/").status_code == 200
    with client.application.app_context():
        user = User.query.filter_by(canvas_id=user_id).one()
        assert (str(CS169A) in user.staff_offerings or user.is_global_admin) == is_staff


def test_staff_can_set_up_their_other_courses(client, mock_canvas):
    # Jimmy Xu is a TA in COMPSCI 168.
    dev_login(client, JIMMY_XU)
    assert 'value="2345678"' in client.get("/offerings/new").get_data(as_text=True)
    client.post("/offerings/new", data={"offerings": ["2345678"]})
    with mock_canvas.app_context():
        assert Offering.query.filter_by(canvas_id=2345678).one().code == "COMPSCI 168"


def test_only_seeded_users_can_sign_in(client, mock_canvas):
    assert dev_login(client, "999").status_code == 400
    assert dev_login(client, None).status_code == 400
    with mock_canvas.app_context():
        assert User.query.count() == 0


def test_no_dev_login_without_the_fake_canvas(client, monkeypatch):
    # TEST_ENV turns the fake Canvas off, as in production.
    assert client.get("/dev_login/").headers["Location"].endswith("/")
    assert dev_login(client, YU_LONG).headers["Location"].endswith("/")
    monkeypatch.setitem(client.application.config, "MOCK_CANVAS", True)
    monkeypatch.setitem(client.application.config, "ENV", "prod")
    assert dev_login(client, YU_LONG).headers["Location"].endswith("/")
    with client.application.app_context():
        assert User.query.count() == 0
