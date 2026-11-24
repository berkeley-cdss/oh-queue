"""Every page of a course opens without errors, settings and descriptions are saved, and
a ticket goes from request to resolved."""

import pytest
from selenium.webdriver.common.by import By

from oh_queue.models import (ConfigEntry, Group, GroupAttendance, GroupAttendanceStatus, GroupStatus, Ticket,
                             TicketStatus, User, db)
from tests.conftest import COURSE

STAFF = ("staff@example.edu", "Staff Member", True)
STUDENT = ("student@example.edu", "Student Person", False)


def add_group(app):
    """An active group of one student, and its id."""
    with app.app_context():
        student = User(email="grouped@example.edu", name="Grouped Student", course="cs61a")
        group = Group(question="3", description="", assignment_id=1, location_id=1, course="cs61a",
                      group_status=GroupStatus.active)
        db.session.add_all([student, group])
        db.session.flush()
        db.session.add(GroupAttendance(group_id=group.id, user_id=student.id, course="cs61a",
                                       group_attendance_status=GroupAttendanceStatus.present))
        db.session.commit()
        return group.id


@pytest.mark.parametrize("path, text", [
    ("/", "Waiting (0)"),
    ("/queue", "Waiting (0)"),
    ("/party", "Party"),
    ("/online_setup", "Online Setup"),
    ("/admin", "Should the queue be open to new tickets?"),
    ("/admin/tickets", "Tickets"),
    ("/admin/party", "Party"),
    ("/admin/assignments", "ID Name Visibility"),
    ("/admin/locations", "Zoom Link (optional)"),
    ("/admin/online", "Online"),
    ("/activity_log", "Activity Log"),
    ("/error?message=Something+broke", "Something broke"),
    ("/presence", "Estimated wait time"),
    ("/no_such_page", "Page Not Found"),
])
def test_staff_pages(site, path, text):
    site.log_in(*STAFF)
    site.visit(COURSE + path)
    assert text in site.text()
    assert site.console_errors() == []


@pytest.mark.parametrize("path, text", [
    ("/", "Fill out the form to request help!"),
    ("/queue", "Fill out the form to request help!"),
    ("/no_such_page", "Page Not Found"),
])
def test_student_pages(site, path, text):
    site.log_in(*STUDENT)
    site.visit(COURSE + path)
    assert text in site.text()
    assert site.console_errors() == []


def test_student_activity_log(site):
    """Students see their own activity, not everyone's."""
    site.log_in(*STUDENT)
    site.visit(COURSE + "/activity_log")
    site.wait(lambda: "/user/" in site.driver.current_url and "student@example.edu" in site.text())
    assert site.console_errors() == []


def test_user_page(site, app):
    site.log_in(*STAFF)
    site.visit(COURSE + "/")
    with app.app_context():
        staff_id = User.query.filter_by(email=STAFF[0]).one().id
    site.visit(f"{COURSE}/user/{staff_id}")
    assert "Staff Member" in site.text()
    assert site.console_errors() == []


def test_group_page(site, app):
    group_id = add_group(app)
    site.log_in(*STAFF)
    site.visit(f"{COURSE}/groups/{group_id}")
    site.wait(lambda: "Grouped Student" in site.text())
    assert site.console_errors() == []


def test_request_and_resolve_ticket(site, app):
    # The student asks for help with Hog question 3 in Cory 247...
    site.log_in(*STUDENT)
    site.visit(COURSE + "/")
    # bootstrap-select hides the selects behind its own menus
    site.driver.execute_script("""
        $("#assignment_id").val("1").selectpicker("refresh");
        $("#location_id").val("1").selectpicker("refresh");
    """)
    site.driver.find_element(By.ID, "question").send_keys("3")
    site.button("Request").click()
    # ...and lands on the ticket's page.
    site.wait(lambda: "/tickets/" in site.driver.current_url)
    site.wait(lambda: "Queued" in site.text())
    with app.app_context():
        ticket_id = Ticket.query.one().id

    # A TA helps them, then resolves the ticket.
    site.log_in(*STAFF)
    site.visit(f"{COURSE}/tickets/{ticket_id}")
    site.button("Help").click()
    site.wait(lambda: "Being helped by you" in site.text())
    site.button("Resolve").click()
    site.wait(lambda: "Resolved by Staff Member" in site.text()
              or site.driver.current_url.rstrip("/").endswith(COURSE))
    with app.app_context():
        assert Ticket.query.one().status.name == "resolved"
    assert site.console_errors() == []


def config_value(app, key):
    with app.app_context():
        return ConfigEntry.query.filter_by(course="cs61a", key=key).one().value


def test_admin_saves_settings(site, app):
    site.log_in(*STAFF)
    site.visit(COURSE + "/admin")

    # a setting with a Save button: the hold delay
    delay = site.driver.find_element(By.CSS_SELECTOR, "input[type=number]")
    delay.clear()
    delay.send_keys("12")
    site.driver.find_elements(By.CSS_SELECTOR, "button[name=btn-submit]")[0].click()
    site.wait(lambda: config_value(app, "juggling_delay") == "12")
    # the button is disabled while saving, then back
    site.wait(lambda: site.driver.find_elements(By.CSS_SELECTOR, "button[name=btn-submit]")[0].is_enabled())

    # a switch: whether the queue is open
    site.driver.find_element(By.CSS_SELECTOR, ".toggle").click()
    site.wait(lambda: config_value(app, "is_queue_open") == "false")
    site.driver.find_element(By.CSS_SELECTOR, ".toggle").click()
    site.wait(lambda: config_value(app, "is_queue_open") == "true")
    assert site.console_errors() == []


def ticket_description(app, ticket_id):
    """From a new session each time, so it isn't a copy the session already loaded."""
    with app.app_context():
        return db.session.get(Ticket, ticket_id).description


def test_ticket_description_is_saved(site, app):
    with app.app_context():
        student = User(email=STUDENT[0], name=STUDENT[1], course="cs61a")
        db.session.add(student)
        db.session.flush()
        ticket = Ticket(user=student, status=TicketStatus.pending, assignment_id=1, location_id=1,
                        question="3", description="Old description", course="cs61a")
        db.session.add(ticket)
        db.session.commit()
        ticket_id = ticket.id

    site.log_in(*STUDENT)
    site.visit(f"{COURSE}/tickets/{ticket_id}")
    box = site.wait(lambda: site.driver.find_element(By.CSS_SELECTOR, "textarea.description-box"))
    assert box.get_attribute("value") == "Old description"
    box.clear()
    box.send_keys("New description")
    site.button("Save Description").click()
    site.wait(lambda: ticket_description(app, ticket_id) == "New description")
    assert site.console_errors() == []


def test_error_page_home_button(site):
    site.log_in(*STAFF)
    site.visit(COURSE + "/no_such_page")
    site.button("Home").click()
    site.wait(lambda: "Waiting (0)" in site.text())
    assert site.driver.current_url.rstrip("/").endswith(COURSE)


def test_signed_out_queue_goes_to_the_party_page(site, app):
    site.visit(COURSE + "/")  # sets up the course's settings
    with app.app_context():
        ConfigEntry.query.filter_by(course="cs61a", key="party_enabled").one().value = "true"
        db.session.commit()
    site.visit(COURSE + "/queue")
    site.wait(lambda: site.driver.current_url.rstrip("/").endswith(COURSE))
    assert "Page Not Found" not in site.text()
    assert site.console_errors() == []


def test_welcome_message_references_without_semicolons(site, app):
    """Messages written for react-markdown 4, which decoded `&nbsp` like `&nbsp;`."""
    site.log_in(*STAFF)
    site.visit(COURSE + "/")  # sets up the course's settings
    with app.app_context():
        ConfigEntry.query.filter_by(course="cs61a", key="welcome").one().value = \
            "Office hours&nbsp&nbsp;today &copy CS 61A &amp `&nbsp` &#160!"
        db.session.commit()
    site.visit(COURSE + "/")
    site.wait(lambda: "Office hours" in site.text())
    # textContent, since Selenium's text turns non-breaking spaces into spaces
    text = site.driver.execute_script("return document.querySelector('.alert-info p').textContent")
    assert text == "Office hours\u00a0\u00a0today \u00a9 CS 61A & &nbsp \u00a0!"
    assert site.console_errors() == []
