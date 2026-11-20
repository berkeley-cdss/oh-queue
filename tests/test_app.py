"""The queue page, its API, and what was removed: the monorepo's common package and appointments."""

import pytest

from oh_queue.models import Assignment, ChatMessage, ConfigEntry, Location, Ticket, User, db
from tests.conftest import COURSE, log_in

REMOVED_CONFIG_KEYS = {
    "show_okpy_backups",
    "okpy_endpoint_id",
    "slack_notif_long_queue",
    "slack_notif_appt_summary",
    "slack_notif_missed_appt",
    "slack_notif_missed_appt_private",
    "appointments_open",
    "daily_appointment_limit",
    "weekly_appointment_limit",
    "simul_appointment_limit",
    "auto_activate_appointments",
    "auto_activate_appointments_frequency",
    "auto_activate_appointments_range",
    "always_show_appointment_join_call",
    "recommend_appointments",
    "appointment_mode_title",
    "appointment_prompt",
    # Courses are only open to people enrolled in them.
    "only_registered_students",
}


def connect(client):
    """The queue's state, as the page loads it."""
    response = client.post(COURSE + "/api/connect", json={"url": "http://localhost/"})
    assert response.status_code == 200
    return {key: value for _, state in response.get_json()["updates"] for key, value in state.items()}


def test_page_renders_with_the_course_name_and_path(client):
    # In development, this also compiles the frontend with Babel.
    response = client.get(COURSE + "/")
    assert response.status_code == 200
    assert b'window.courseName = "CS 61A";' in response.data
    assert b'window.basePath = "/offerings/101";' in response.data


def test_first_visit_sets_up_the_course_without_removed_settings(client):
    client.get(COURSE + "/")
    with client.application.app_context():
        keys = {entry.key for entry in ConfigEntry.query.filter_by(course="cs61a")}
    assert "is_queue_open" in keys
    assert not keys & REMOVED_CONFIG_KEYS


def test_state_sent_to_the_page_has_no_removed_settings_or_appointments(client):
    client.get(COURSE + "/")
    log_in(client)
    state = connect(client)
    assert state["config"]["is_queue_open"] == "true"
    assert not set(state["config"]) & REMOVED_CONFIG_KEYS
    assert "appointments" not in state


def test_staff_can_change_settings(client):
    client.get(COURSE + "/")
    log_in(client)
    response = client.post(COURSE + "/api/update_config", json={"key": "show_presence", "value": "false"})
    assert response.status_code == 200
    assert connect(client)["config"]["show_presence"] == "false"


def test_students_cant_change_settings(client):
    client.get(COURSE + "/")
    log_in(client, "student@example.edu", is_staff=False)
    response = client.post(COURSE + "/api/update_config", json={"key": "is_queue_open", "value": "false"})
    assert "permission" in response.get_json()["action"]["messages"][0]["text"]
    with client.application.app_context():
        assert ConfigEntry.query.filter_by(key="is_queue_open").one().value == "true"


@pytest.mark.parametrize("path", [
    "/api/test_slack",
    "/api/appointment_summary",
    "/api/sudo/connect",
    "/jobs/slack_notify",
    "/oauth/login",
    "/oauth/authorized",
    "/api/user",
    "/api/assign_staff_appointment",
    "/api/unassign_staff_appointment",
    "/api/assign_appointment",
    "/api/unassign_appointment",
    "/api/load_appointment",
    "/api/set_appointment_status",
    "/api/mark_attendance",
    "/api/toggle_visibility",
    "/api/delete_appointment",
    "/api/upload_appointments",
    "/api/bulk_appointment_action",
    "/api/update_appointment",
    "/api/update_appointments",
    "/jobs/auto_activate_appointments",
    # The per-course sites' login routes and debug page.
    "/oauth/canvas_login",
    "/oauth/canvas_authorized",
    "/oauth/logout",
    "/debug",
])
def test_removed_endpoints(client, path):
    log_in(client)
    if path.startswith("/api/"):
        path = COURSE + path
    assert client.post(path, json={}).status_code in (404, 405)


def test_clear_inactive_groups_job_runs(client):
    client.get(COURSE + "/")
    assert client.post("/jobs/clear_inactive_groups").status_code == 200


def make_ticket(client):
    with client.application.app_context():
        assignment = Assignment(name="Hog", visible=True, course="cs61a")
        location = Location(name="Cory", visible=True, online=False, link="", course="cs61a")
        db.session.add_all([assignment, location])
        db.session.commit()
        return assignment.id, location.id


def test_chat_messages_go_on_tickets_but_not_appointments(client):
    client.get(COURSE + "/")
    log_in(client, "student@example.edu", is_staff=False)
    assignment_id, location_id = make_ticket(client)
    response = client.post(COURSE + "/api/create", json={
        "assignment_id": assignment_id, "location_id": location_id, "question": "1", "description": "",
    })
    ticket_id = response.get_json()["action"]["redirect"].strip("/").split("/")[-1]

    client.post(COURSE + "/api/send_chat_message", json={"mode": "ticket", "id": int(ticket_id), "content": "hi"})
    for request in ({"mode": "appointment", "id": 1, "content": "hi"}, {"mode": "appointment", "content": "hi"}):
        response = client.post(COURSE + "/api/send_chat_message", json=request)
        assert "ticket or group" in response.get_json()["action"]["messages"][0]["text"]

    with client.application.app_context():
        assert [(m.body, m.ticket_id) for m in ChatMessage.query.all()] == [("hi", int(ticket_id))]


def test_user_history_has_tickets_only(client):
    client.get(COURSE + "/")
    log_in(client)
    with client.application.app_context():
        user_id = User.query.one().id
    response = client.post(COURSE + "/api/get_user", json=user_id)
    assert set(response.get_json()["action"]) == {"user", "tickets"}


def test_queue_state_includes_tickets_without_a_group(client):
    client.get(COURSE + "/")
    log_in(client, "student@example.edu", is_staff=False)
    assignment_id, location_id = make_ticket(client)
    client.post(COURSE + "/api/create", json={
        "assignment_id": assignment_id, "location_id": location_id, "question": "1", "description": "",
    })
    log_in(client)
    # The query outer-joins each ticket's group, which gives NULL for the
    # group's status when there's none.
    tickets = connect(client)["tickets"]
    assert [(t["status"], t["group_id"]) for t in tickets] == [("pending", None)]


def test_only_juggled_tickets_can_be_rerequested(client):
    client.get(COURSE + "/")
    log_in(client, "student@example.edu", is_staff=False)
    assignment_id, location_id = make_ticket(client)
    response = client.post(COURSE + "/api/create", json={
        "assignment_id": assignment_id, "location_id": location_id, "question": "1", "description": "",
    })
    ticket_id = int(response.get_json()["action"]["redirect"].strip("/").split("/")[-1])
    response = client.post(COURSE + "/api/rerequest", json={"ticket_ids": [ticket_id]})
    assert response.status_code == 200
    assert "permission" in response.get_json()["action"]["messages"][0]["text"]
    with client.application.app_context():
        assert Ticket.query.one().status.name == "pending"


def test_asking_twice_points_to_the_ticket_already_on_the_queue(client):
    client.get(COURSE + "/")
    log_in(client, "student@example.edu", is_staff=False)
    assignment_id, location_id = make_ticket(client)
    form = {"assignment_id": assignment_id, "location_id": location_id, "question": "1", "description": ""}
    first = client.post(COURSE + "/api/create", json=form).get_json()["action"]["redirect"]
    second = client.post(COURSE + "/api/create", json=form).get_json()["action"]
    assert second["messages"][0]["text"] == "You are already on the queue"
    assert second["redirect"] == first
