"""One site for every course: the offering pages, and each course's queue kept to itself."""

import pytest

from oh_queue.models import (
    MAX_OFFERING_CANVAS_ID,
    Assignment,
    ConfigEntry,
    Location,
    Offering,
    Ticket,
    User,
    db,
)
from tests.conftest import COURSE, canvas_sign_in, log_in, role

OTHER = "/offerings/202"


@pytest.fixture()
def two_courses(app):
    """A second offering, Data 8 (Canvas course 202), set up in this app."""
    with app.app_context():
        db.session.add(Offering(canvas_id=202, key="202", name="DATA C8 - LEC 001", code="DATA C8"))
        db.session.commit()


def offerings_page(client):
    response = client.get("/offerings")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def section(page, heading, next_heading=None):
    """The part of the offerings page under ``heading``."""
    start = page.index(heading)
    return page[start:page.index(next_heading, start)] if next_heading else page[start:]


def test_landing_page_and_offerings_need_a_sign_in(client):
    landing = client.get("/")
    assert landing.status_code == 200
    assert b"Welcome to the Office Hours Queue!" in landing.data
    response = client.get("/offerings")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login/?next=/offerings")

    canvas_sign_in(client, "ta@example.edu", {})
    response = client.get("/")
    assert response.headers["Location"].endswith("/offerings")


def test_offerings_page_lists_staff_student_and_other_courses(client, two_courses):
    with client.application.app_context():
        db.session.add(Offering(canvas_id=303, key="303", name="Not mine", code="CS 303"))
        db.session.commit()
    canvas_sign_in(client, "ta@example.edu", {
        "101": role(is_staff=True),
        "202": role(is_student=True, name="DATA C8 - LEC 001", code="DATA C8"),
        "404": role(is_staff=True, name="Not set up", code="CS 404"),
        "505": role(name="Observed", code="CS 505"),
    })
    page = offerings_page(client)
    staff = section(page, "Staff Course Offerings", "Student Course Offerings")
    students = section(page, "Student Course Offerings", "Other Course Offerings")
    assert f'href="{COURSE}/"' in staff
    assert f'href="{OTHER}/"' in students
    # Courses not set up, and set-up courses the user isn't in, aren't listed.
    assert "Not set up" not in page and "Not mine" not in page


def test_linked_offerings_get_their_canvas_details_when_listed(client):
    with client.application.app_context():
        offering = db.session.get(Offering, 1)
        offering.name, offering.code, offering.start_at = "cs61a", None, None
        db.session.commit()
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_staff=True, start_at="2026-08-19T07:00:00Z")})
    page = offerings_page(client)
    assert "2026-08" in page and "COMPSCI 61A - LEC 001" in page
    with client.application.app_context():
        offering = db.session.get(Offering, 1)
        assert (offering.key, offering.code) == ("cs61a", "COMPSCI 61A")


def test_staff_import_their_courses_and_students_cant(client):
    courses = {
        "101": role(is_staff=True),  # already set up
        "202": role(is_staff=True, name="DATA C8 - LEC 001", code="DATA C8"),
        "303": role(is_student=True, name="Taking", code="CS 303"),
    }
    canvas_sign_in(client, "ta@example.edu", courses)
    page = client.get("/offerings/new").get_data(as_text=True)
    assert 'value="202"' in page
    assert 'value="101"' not in page and 'value="303"' not in page

    response = client.post("/offerings/new", data={"offerings": ["202", "303", "101"]})
    assert response.status_code == 302
    with client.application.app_context():
        assert [(o.canvas_id, o.key, o.code) for o in Offering.query.order_by(Offering.id)] == [
            (101, "cs61a", "CS 61A"), (202, "202", "DATA C8")]
    assert client.get(OTHER + "/").status_code == 200


def test_courses_with_too_big_ids_cant_be_imported_or_opened(client):
    too_big = str(MAX_OFFERING_CANVAS_ID + 1)
    canvas_sign_in(client, "ta@example.edu", {too_big: role(is_staff=True)})
    response = client.post("/offerings/new", data={"offerings": [too_big]})
    assert response.status_code == 302
    with client.application.app_context():
        assert Offering.query.count() == 1
    assert client.get(f"/offerings/{too_big}/").status_code == 404
    assert client.post(f"/offerings/{too_big}/remove").status_code == 404


def test_only_course_admins_remove_offerings_and_their_data_is_kept(client, two_courses):
    canvas_sign_in(client, "ta@example.edu", {"202": role(is_staff=True)})
    assert 'action="/offerings/202/remove"' not in offerings_page(client)
    assert client.post(OTHER + "/remove").status_code == 403

    log_in(client)  # makes the course's settings
    canvas_sign_in(client, "prof@example.edu", {"202": role(is_staff=True, is_admin=True)}, canvas_user_id=7)
    client.get(OTHER + "/")
    assert 'action="/offerings/202/remove"' in offerings_page(client)
    assert client.post(OTHER + "/remove").status_code == 302
    assert client.get(OTHER + "/").status_code == 404
    with client.application.app_context():
        assert ConfigEntry.query.filter_by(course="202").count() > 0

    # Importing it again brings it back, under the same key.
    client.post("/offerings/new", data={"offerings": ["202"]})
    assert client.get(OTHER + "/").status_code == 200


def test_unknown_offerings_are_not_found(client):
    assert client.get("/offerings/999/").status_code == 404
    assert client.post("/offerings/999/api/connect", json={}).status_code == 404


def make_ticket(client, course_key, prefix):
    with client.application.app_context():
        assignment = Assignment(name="Hog", visible=True, course=course_key)
        location = Location(name="Cory", visible=True, online=False, link="", course=course_key)
        db.session.add_all([assignment, location])
        db.session.commit()
        ids = {"assignment_id": assignment.id, "location_id": location.id}
    response = client.post(prefix + "/api/create", json={**ids, "question": "1", "description": ""})
    return response.get_json()["action"]


def connect(client, prefix):
    response = client.post(prefix + "/api/connect", json={"url": "http://localhost/"})
    return {key: value for _, state in response.get_json()["updates"] for key, value in state.items()}


def test_each_course_has_its_own_queue_users_and_roles(app, two_courses):
    student, ta = app.test_client(), app.test_client()
    log_in(student, "student@example.edu", is_staff=False)
    student.get(OTHER + "/")
    canvas_sign_in(ta, "ta@example.edu", {"101": role(is_staff=True), "202": role(is_student=True)})
    ta.get(COURSE + "/")
    ta.get(OTHER + "/")

    action = make_ticket(student, "cs61a", COURSE)
    # Redirects are paths in the course, for the page's router, which adds the course's path.
    ticket_id = int(action["redirect"].strip("/").split("/")[-1])
    assert action["redirect"] == f"/tickets/{ticket_id}/"

    assert [t["id"] for t in connect(ta, COURSE)["tickets"]] == [ticket_id]
    assert connect(ta, OTHER)["tickets"] == []
    assert connect(ta, COURSE)["current_user"]["isStaff"]
    assert not connect(ta, OTHER)["current_user"]["isStaff"]

    # A ticket can't be reached through another course's API.
    response = ta.post(OTHER + "/api/assign", json=[ticket_id]).get_json()["action"]
    assert "permission" in response["messages"][0]["text"]
    with app.app_context():
        assert Ticket.query.one().status.name == "pending"
        assert {(u.email, u.course, u.is_staff) for u in User.query} == {
            ("student@example.edu", "cs61a", False), ("student@example.edu", "202", False),
            ("ta@example.edu", "cs61a", True), ("ta@example.edu", "202", False)}


def test_link_offering_command(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["link-offering", "202", "data8", "Data 8"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        assert Offering.query.filter_by(canvas_id=202).one().key == "data8"
    for args in (["202", "other", "x"], ["303", "data8", "x"], [str(MAX_OFFERING_CANVAS_ID + 1), "big", "x"]):
        result = runner.invoke(args=["link-offering", *args])
        assert result.exit_code != 0


def test_importing_a_course_someone_else_just_imported_is_not_an_error(client):
    canvas_sign_in(client, "ta@example.edu", {"202": role(is_staff=True, name="DATA C8 - LEC 001", code="DATA C8")})
    # Imported between this page loading and the form being sent: here, as a
    # different course whose key is taken, since the page lists only new ones.
    with client.application.app_context():
        db.session.add(Offering(canvas_id=303, key="202", name="Taken"))
        db.session.commit()
    response = client.post("/offerings/new", data={"offerings": ["202"]})
    assert response.status_code == 302
    page = offerings_page(client)
    assert "Someone else just imported" in page
    with client.application.app_context():
        assert Offering.query.filter_by(canvas_id=202).count() == 0
