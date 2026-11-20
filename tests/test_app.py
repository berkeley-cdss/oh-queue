"""The queue page, its API, and what was removed: the monorepo's common package and appointments."""

import pytest

from oh_queue.course import format_coursecode, get_canvas_course_id, get_course
from oh_queue.models import Assignment, ChatMessage, ConfigEntry, Location, User, db
from tests.conftest import log_in

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
}


def connect(client):
    """The queue's state, as the page loads it."""
    response = client.post("/api/connect", json={"url": "http://localhost/"})
    assert response.status_code == 200
    return {key: value for _, state in response.get_json()["updates"] for key, value in state.items()}


def test_page_renders_with_the_course_name(client):
    # In development, this also compiles the frontend with Babel.
    response = client.get("/")
    assert response.status_code == 200
    assert b"CS 61A" in response.data


def test_first_visit_sets_up_the_course_without_removed_settings(client):
    client.get("/")
    with client.application.app_context():
        keys = {entry.key for entry in ConfigEntry.query.filter_by(course="cs61a")}
    assert "is_queue_open" in keys
    assert not keys & REMOVED_CONFIG_KEYS


def test_state_sent_to_the_page_has_no_removed_settings_or_appointments(client):
    client.get("/")
    log_in(client)
    state = connect(client)
    assert state["config"]["is_queue_open"] == "true"
    assert not set(state["config"]) & REMOVED_CONFIG_KEYS
    assert "appointments" not in state


def test_staff_can_change_settings(client):
    client.get("/")
    log_in(client)
    response = client.post("/api/update_config", json={"key": "show_presence", "value": "false"})
    assert response.status_code == 200
    assert connect(client)["config"]["show_presence"] == "false"


def test_students_cant_change_settings(client):
    client.get("/")
    log_in(client, "student@example.edu", is_staff=False)
    response = client.post("/api/update_config", json={"key": "is_queue_open", "value": "false"})
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
])
def test_removed_endpoints(client, path):
    log_in(client)
    assert client.post(path, json={}).status_code in (404, 405)


def test_clear_inactive_groups_job_runs(client):
    client.get("/")
    assert client.post("/jobs/clear_inactive_groups").status_code == 200


def test_course_comes_from_config(app, monkeypatch):
    assert (get_course(), get_canvas_course_id()) == ("cs61a", 101)
    monkeypatch.setitem(app.config, "COURSE_KEY", "data8")
    monkeypatch.setitem(app.config, "CANVAS_COURSE_ID", 5)
    assert (get_course(), get_canvas_course_id()) == ("data8", 5)


@pytest.mark.parametrize("key, name", [
    ("cs61a", "CS 61A"),
    ("data8", "DATA 8"),
    ("eecs16b", "EECS 16B"),
    ("cs189", "CS 189 (CDSS)"),
    ("eecs189", "CS 189/289A"),
    ("unusual-key", "unusual-key"),
])
def test_format_coursecode(key, name):
    assert format_coursecode(key) == name


def make_ticket(client):
    with client.application.app_context():
        assignment = Assignment(name="Hog", visible=True, course="cs61a")
        location = Location(name="Cory", visible=True, online=False, link="", course="cs61a")
        db.session.add_all([assignment, location])
        db.session.commit()
        return assignment.id, location.id


def test_chat_messages_go_on_tickets_but_not_appointments(client):
    client.get("/")
    log_in(client, "student@example.edu", is_staff=False)
    assignment_id, location_id = make_ticket(client)
    response = client.post("/api/create", json={
        "assignment_id": assignment_id, "location_id": location_id, "question": "1", "description": "",
    })
    ticket_id = response.get_json()["action"]["redirect"].strip("/").split("/")[-1]

    client.post("/api/send_chat_message", json={"mode": "ticket", "id": int(ticket_id), "content": "hi"})
    for request in ({"mode": "appointment", "id": 1, "content": "hi"}, {"mode": "appointment", "content": "hi"}):
        response = client.post("/api/send_chat_message", json=request)
        assert "ticket or group" in response.get_json()["action"]["messages"][0]["text"]

    with client.application.app_context():
        assert [(m.body, m.ticket_id) for m in ChatMessage.query.all()] == [("hi", int(ticket_id))]


def test_user_history_has_tickets_only(client):
    client.get("/")
    log_in(client)
    with client.application.app_context():
        user_id = User.query.one().id
    response = client.post("/api/get_user", json=user_id)
    assert set(response.get_json()["action"]) == {"user", "tickets"}


def test_queue_state_includes_tickets_without_a_group(client):
    client.get("/")
    log_in(client, "student@example.edu", is_staff=False)
    assignment_id, location_id = make_ticket(client)
    client.post("/api/create", json={
        "assignment_id": assignment_id, "location_id": location_id, "question": "1", "description": "",
    })
    log_in(client)
    # The query outer-joins each ticket's group, which gives NULL for the
    # group's status when there's none.
    tickets = connect(client)["tickets"]
    assert [(t["status"], t["group_id"]) for t in tickets] == [("pending", None)]
