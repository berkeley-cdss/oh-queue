"""The queue page, its API, and what was removed with the monorepo's common package."""

import pytest

from oh_queue.course import format_coursecode, get_canvas_course_id, get_course
from oh_queue.models import ConfigEntry
from tests.conftest import log_in

REMOVED_CONFIG_KEYS = {
    "show_okpy_backups",
    "okpy_endpoint_id",
    "slack_notif_long_queue",
    "slack_notif_appt_summary",
    "slack_notif_missed_appt",
    "slack_notif_missed_appt_private",
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


def test_first_visit_sets_up_the_course_without_slack_or_okpy_settings(client):
    client.get("/")
    with client.application.app_context():
        keys = {entry.key for entry in ConfigEntry.query.filter_by(course="cs61a")}
    assert "is_queue_open" in keys
    assert not keys & REMOVED_CONFIG_KEYS


def test_config_sent_to_the_page_has_no_slack_or_okpy_settings(client):
    client.get("/")
    log_in(client)
    config = connect(client)["config"]
    assert config["is_queue_open"] == "true"
    assert not set(config) & REMOVED_CONFIG_KEYS


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
])
def test_removed_endpoints(client, path):
    log_in(client)
    assert client.post(path, json={}).status_code in (404, 405)


@pytest.mark.parametrize("job", ["clear_inactive_groups", "auto_activate_appointments"])
def test_jobs_run(client, job):
    client.get("/")
    assert client.post(f"/jobs/{job}").status_code == 200


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
