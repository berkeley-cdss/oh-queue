"""One user per person across courses: roles in each course, who's online in each,
looking people up, and merging two rows for one person."""

import datetime
from unittest.mock import patch

import pytest
from flask import g

from oh_queue.models import (
    Assignment,
    Group,
    GroupAttendance,
    GroupAttendanceStatus,
    GroupStatus,
    Heartbeat,
    Location,
    Offering,
    Ticket,
    TicketStatus,
    User,
    db,
    utcnow,
)
from tests.conftest import COURSE, canvas_sign_in, log_in, role

OTHER = "/offerings/202"


@pytest.fixture()
def two_courses(app):
    """A second offering, Data 8 (Canvas course 202), set up in this app."""
    with app.app_context():
        db.session.add(Offering(canvas_id=202, key="202", name="DATA C8 - LEC 001", code="DATA C8"))
        db.session.commit()


def api(client, name, payload, prefix=COURSE):
    return client.post(f"{prefix}/api/{name}", json=payload).get_json()["action"]


def connect(client, prefix=COURSE):
    """The queue's state, as the page loads it (which sets up the course's settings)."""
    assert client.get(prefix + "/").status_code == 200
    response = client.post(prefix + "/api/connect", json={"url": "http://localhost/"})
    assert response.status_code == 200
    return {key: value for _, state in response.get_json()["updates"] for key, value in state.items()}


def user_id(app, email):
    with app.app_context():
        return User.query.filter_by(email=email).one().id


def add_ticket(app, user, helper=None, course="cs61a"):
    """A resolved ticket in ``course`` from ``user``, helped by ``helper`` (emails)."""
    with app.app_context():
        assignment = Assignment(name="Hog", visible=True, course=course)
        location = Location(name="Cory", visible=True, online=False, link="", course=course)
        db.session.add_all([assignment, location])
        db.session.flush()
        ticket = Ticket(status=TicketStatus.resolved, assignment_id=assignment.id, location_id=location.id,
                        question="1", course=course, user_id=User.query.filter_by(email=user).one().id,
                        helper_id=helper and User.query.filter_by(email=helper).one().id)
        db.session.add(ticket)
        db.session.commit()
        return ticket.id


# Roles


def in_course(app, key, fn):
    """``fn()``'s result inside course ``key``'s pages, as views see it."""
    with app.test_request_context():
        g.offering = Offering.query.filter_by(key=key).one()
        return fn()


def test_staff_and_admin_answer_for_the_current_course(app, two_courses):
    with app.app_context():
        user = User(email="ta@example.edu", name="TA")
        user.set_role("cs61a", is_staff=True, is_admin=True)
        user.set_role("202", is_staff=False)
        db.session.add(user)
        db.session.commit()
        assert in_course(app, "cs61a", lambda: (user.is_staff, user.is_admin)) == (True, True)
        assert in_course(app, "202", lambda: (user.is_staff, user.is_admin)) == (False, False)
        # Outside any course, nobody is staff.
        assert (user.is_staff, user.is_admin) == (False, False)
        user.is_global_admin = True
        assert in_course(app, "202", lambda: (user.is_staff, user.is_admin)) == (True, True)


def test_a_role_change_moves_someone_between_staff_and_students(app_context):
    user = User(email="ta@example.edu", name="TA")
    user.set_role("cs61a", is_staff=True, is_admin=True)
    assert (user.staff_offerings, user.admin_offerings, user.student_offerings) == ({"cs61a"}, {"cs61a"}, set())
    user.set_role("cs61a", is_staff=False)
    assert (user.staff_offerings, user.admin_offerings, user.student_offerings) == (set(), set(), {"cs61a"})
    assert user.is_member_of("cs61a") and not user.is_member_of("202")


def test_signing_in_again_updates_the_role_in_canvas(client):
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_staff=True, is_admin=True)})
    connect(client)
    canvas_sign_in(client, "ta@example.edu", {"101": role(is_staff=True)})
    connect(client)
    with client.application.app_context():
        user = User.query.one()
        assert (user.staff_offerings, user.admin_offerings) == ({"cs61a"}, set())


def test_global_admins_get_no_role_of_their_own(client):
    canvas_sign_in(client, "admin@example.edu", {"999": role(is_student=True)})
    assert connect(client)["current_user"]["isStaff"]
    with client.application.app_context():
        user = User.query.one()
        assert (user.staff_offerings, user.student_offerings) == (set(), set())


@pytest.mark.parametrize("name, short_name", [
    ("Ada Lovelace", "Ada"), ("ada@example.edu", "ada"), ("", ""),
])
def test_short_names(name, short_name):
    assert User(email="a@example.edu", name=name).short_name == short_name


def test_global_admins_see_every_offering_as_staff(client, two_courses):
    canvas_sign_in(client, "admin@example.edu", {"999": role(is_student=True), "202": role(is_student=True)})
    page = client.get("/offerings").get_data(as_text=True)
    staff = page[page.index("Staff Course Offerings"):]
    assert "COMPSCI 61A - LEC 001" in staff and "DATA C8 - LEC 001" in staff


# Looking people up


def test_staff_list_the_course_s_staff_and_students(app, two_courses):
    ta, student, other = app.test_client(), app.test_client(), app.test_client()
    log_in(ta, "ta@example.edu", is_staff=True)
    log_in(student, "student@example.edu", is_staff=False)
    canvas_sign_in(other, "other@example.edu", {"202": role(is_student=True)}, canvas_user_id=3)
    other.get(OTHER + "/")
    assert {u["email"] for u in api(ta, "list_users", {})} == {"ta@example.edu", "student@example.edu"}
    assert "permission" in api(student, "list_users", {})["messages"][0]["text"]


def test_anyone_can_see_their_own_history_but_not_others(app):
    alice, bob = app.test_client(), app.test_client()
    log_in(alice, "alice@example.edu", is_staff=False)
    log_in(bob, "bob@example.edu", is_staff=False)
    ticket_id = add_ticket(app, "alice@example.edu")
    history = api(alice, "get_user", user_id(app, "alice@example.edu"))
    assert [t["id"] for t in history["tickets"]] == [ticket_id]
    assert "permission" in api(bob, "get_user", user_id(app, "alice@example.edu"))["messages"][0]["text"]


def test_staff_see_the_history_of_anyone_in_or_helped_in_the_course(app, two_courses):
    ta, other, admin = app.test_client(), app.test_client(), app.test_client()
    log_in(ta, "ta@example.edu", is_staff=True)
    canvas_sign_in(other, "other@example.edu", {"202": role(is_student=True)}, canvas_user_id=3)
    other.get(OTHER + "/")
    canvas_sign_in(admin, "admin@example.edu", {"999": role(is_student=True)}, canvas_user_id=4)

    # Someone only in another course, or no one at all.
    for missing in (user_id(app, "other@example.edu"), 12345):
        assert "No such user" in api(ta, "get_user", missing)["messages"][0]["text"]
    # A global admin has no role in the course, but helped in it.
    ticket_id = add_ticket(app, "other@example.edu", helper="admin@example.edu")
    history = api(ta, "get_user", user_id(app, "admin@example.edu"))
    assert (history["user"]["email"], [t["id"] for t in history["tickets"]]) == ("admin@example.edu", [ticket_id])
    # Their tickets in other courses stay out of it.
    add_ticket(app, "other@example.edu", helper="admin@example.edu", course="202")
    assert len(api(ta, "get_user", user_id(app, "other@example.edu"))["tickets"]) == 1


def test_signed_out_visitors_cant_use_what_needs_a_sign_in(client):
    connect(client)
    response = api(client, "send_chat_message", {"mode": "ticket", "id": 1, "content": "hi"})
    assert "permission" in response["messages"][0]["text"]


# Who's online


def test_who_is_online_is_counted_in_each_course(app, two_courses):
    ta, student, admin = app.test_client(), app.test_client(), app.test_client()
    canvas_sign_in(ta, "ta@example.edu", {"101": role(is_staff=True), "202": role(is_student=True)}, canvas_user_id=1)
    canvas_sign_in(student, "student@example.edu", {"101": role(is_student=True), "202": role(is_student=True)},
                   canvas_user_id=2)
    canvas_sign_in(admin, "admin@example.edu", {"999": role(is_student=True)}, canvas_user_id=3)
    connect(ta, COURSE)
    connect(student, OTHER)
    connect(admin, OTHER)

    cs61a = connect(ta, COURSE)["presence"]
    assert (cs61a["students"], cs61a["staff"], cs61a["staff_list"]) == (0, 1, [["ta@example.edu", "Ta"]])
    # The TA is a student in data8, and the global admin is staff everywhere.
    data8 = connect(admin, OTHER)["presence"]
    assert (data8["students"], data8["staff"], data8["staff_list"]) == (1, 1, [["admin@example.edu", "Admin"]])
    connect(ta, OTHER)
    assert connect(admin, OTHER)["presence"]["students"] == 2


def test_heartbeats_older_than_30_seconds_dont_count(client):
    log_in(client, "student@example.edu", is_staff=False)
    assert connect(client)["presence"]["students"] == 1
    with client.application.app_context():
        Heartbeat.query.one().time = utcnow() - datetime.timedelta(seconds=31)
        db.session.commit()
    with patch.object(Heartbeat, "beat"):  # this connect doesn't beat
        assert connect(client)["presence"]["students"] == 0


def test_a_heartbeat_another_tab_just_made_is_kept(client):
    log_in(client, "student@example.edu", is_staff=False)
    with client.application.app_context():
        db.session.query(Heartbeat).delete()
        db.session.commit()
    beat = Heartbeat.beat

    def other_tab_first(user, course):
        beat(user, course)
        # The other tab's heartbeat lands between this one's check and its commit.
        with db.engine.begin() as connection:
            connection.execute(Heartbeat.__table__.insert().values(user_id=user.id, course=course, time=utcnow()))

    with patch.object(Heartbeat, "beat", other_tab_first):
        state = connect(client)
    assert state["current_user"]["email"] == "student@example.edu"
    with client.application.app_context():
        assert Heartbeat.query.count() == 1


def make_group(app, course, *members):
    """An active group in ``course`` with ``members`` (emails) present."""
    with app.app_context():
        location = Location(name="Cory", visible=True, online=False, link="", course=course)
        db.session.add(location)
        db.session.flush()
        group = Group(question="1", location_id=location.id, course=course, group_status=GroupStatus.active)
        db.session.add(group)
        db.session.flush()
        for email in members:
            db.session.add(GroupAttendance(group_id=group.id, user_id=User.query.filter_by(email=email).one().id,
                                           course=course, group_attendance_status=GroupAttendanceStatus.present))
        db.session.commit()
        return group.id


def test_groups_close_once_everyone_in_them_has_left_the_course_s_queue(app, two_courses):
    student = app.test_client()
    canvas_sign_in(student, "student@example.edu", {"101": role(is_student=True), "202": role(is_student=True)})
    connect(student, COURSE)
    open_here = make_group(app, "cs61a", "student@example.edu")
    # Only open in cs61a: data8's queue hasn't been opened for 3 minutes.
    open_elsewhere = make_group(app, "202", "student@example.edu")
    with app.app_context():
        heartbeat = Heartbeat(user_id=User.query.one().id, course="202",
                              time=utcnow() - datetime.timedelta(minutes=4))
        db.session.add(heartbeat)
        db.session.commit()
    assert student.post("/jobs/clear_inactive_groups").status_code == 200
    with app.app_context():
        assert db.session.get(Group, open_here).group_status == GroupStatus.active
        assert db.session.get(Group, open_elsewhere).group_status == GroupStatus.resolved


# Merging two rows for one person


def test_merging_keeps_the_newer_heartbeat_in_a_course_both_had(app_context):
    keep, other = User(email="a@example.edu", name="A"), User(email="b@example.edu", name="B")
    keep.set_role("cs61a", is_staff=False)
    other.set_role("cs61a", is_staff=True)
    other.set_role("202", is_staff=False, is_admin=False)
    db.session.add_all([keep, other])
    db.session.flush()
    now, older = utcnow(), utcnow() - datetime.timedelta(minutes=1)
    db.session.add_all([
        Heartbeat(user_id=keep.id, course="cs61a", time=older),
        Heartbeat(user_id=other.id, course="cs61a", time=now),
        Heartbeat(user_id=keep.id, course="202", time=now),
        Heartbeat(user_id=other.id, course="202", time=older),
    ])
    db.session.commit()
    other_id = other.id

    keep.absorb(other)
    db.session.commit()

    assert db.session.get(User, other_id) is None
    assert sorted((h.user_id, h.course, h.time) for h in Heartbeat.query) == sorted([
        (keep.id, "cs61a", now), (keep.id, "202", now)])
    # Staff where either was; a student only where neither was staff.
    assert (keep.staff_offerings, keep.student_offerings) == ({"cs61a"}, {"202"})
