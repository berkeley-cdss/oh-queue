"""Every page of a course opens without errors, settings and descriptions are saved, and
a ticket goes from request to resolved."""

import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select

from oh_queue.models import (Assignment, ConfigEntry, Group, GroupAttendance, GroupAttendanceStatus, GroupStatus, Ticket,
                             TicketStatus, User, db)
from tests.conftest import COURSE

STAFF = ("staff@example.edu", "Staff Member", True)
STUDENT = ("student@example.edu", "Student Person", False)


def add_group(app, question="3"):
    """An active group of one student, and its id."""
    with app.app_context():
        student = User(email="grouped@example.edu", name="Grouped Student", course="cs61a")
        group = Group(question=question, description="", assignment_id=1, location_id=1, course="cs61a",
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
    Select(site.driver.find_element(By.ID, "assignment_id")).select_by_visible_text("Hog")
    Select(site.driver.find_element(By.ID, "location_id")).select_by_visible_text("Cory 247")
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
    switch = site.driver.find_element(By.CSS_SELECTOR, "input[role=switch]")
    switch.click()
    site.wait(lambda: config_value(app, "is_queue_open") == "false")
    label = site.driver.find_element(By.CSS_SELECTOR, f"label[for='{switch.get_attribute('id')}']").text
    # the setting's name, for screen readers, then the state shown
    assert label.startswith("Queue open to new tickets")
    assert label.endswith("Closed")
    switch.click()
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
            "Office hours&nbsp&nbsp;today &copy CS 61A &amp `&nbsp` &#160!\n\n" \
            "[Zoom](https://berkeley.zoom.us/j/1?pwd=x&region=us)"
        db.session.commit()
    site.visit(COURSE + "/")
    site.wait(lambda: "Office hours" in site.text())
    # textContent, since Selenium's text turns non-breaking spaces into spaces
    text = site.driver.execute_script("return document.querySelector('.alert-info p').textContent")
    assert text == "Office hours\u00a0\u00a0today \u00a9 CS 61A & &nbsp \u00a0!"
    # but not in links' addresses
    link = site.driver.find_element(By.LINK_TEXT, "Zoom")
    assert link.get_attribute("href") == "https://berkeley.zoom.us/j/1?pwd=x&region=us"
    assert site.console_errors() == []


def test_group_that_does_not_exist(site):
    """Staff see that it isn't found, after asking for it once."""
    site.watch_requests()
    site.log_in(*STAFF)
    site.visit(f"{COURSE}/groups/12345")
    site.wait(lambda: "Not found" in site.text())
    time.sleep(2)
    assert site.requests("load_group") == 1
    assert site.console_errors() == []


def test_group_page_with_an_id_that_is_not_a_number(site):
    site.log_in(*STAFF)
    site.visit(f"{COURSE}/groups/abc")
    site.wait(lambda: "Not found" in site.text())


def test_group_page_asks_again_after_a_failed_request(site):
    """A group that doesn't exist: the first request fails, as if the network were down,
    and the page asks again once it's back online."""
    site.watch_requests(fail={"load_group": 1})
    site.log_in(*STAFF)
    site.visit(f"{COURSE}/groups/12345")
    # the page polls every ten seconds, which brings it back online
    site.wait(lambda: "Not found" in site.text(), timeout=25)
    assert site.requests("load_group") == 2


def test_group_without_a_question(site, app):
    add_group(app, question="")
    site.log_in(*STAFF)
    site.visit(COURSE + "/party")
    # the group's card, which shows its assignment, question and location
    card = site.wait(lambda: next(iter(site.driver.find_elements(By.CSS_SELECTOR, ".card-holder .card")), None))
    site.wait(lambda: "Hog" in card.text and "Cory 247" in card.text)
    assert "QNaN" not in card.text


def test_failed_setting_save_can_be_tried_again(site):
    site.watch_requests(fail={"update_config": 1})
    site.log_in(*STAFF)
    site.visit(COURSE + "/admin")
    delay = site.driver.find_element(By.CSS_SELECTOR, "input[type=number]")
    delay.clear()
    delay.send_keys("12")
    save = site.driver.find_elements(By.CSS_SELECTOR, "button[name=btn-submit]")[0]
    save.click()
    site.wait(lambda: site.requests("update_config") == 1)
    site.wait(lambda: save.is_enabled() and "is-loading" not in save.get_attribute("class"))


def test_next_ticket_shows_the_next_tickets_assignment(site, app):
    """Not the previous ticket's, left over from its page."""
    with app.app_context():
        maps = Assignment(name="Maps", course="cs61a", visible=True)
        db.session.add(maps)
        tickets = []
        for email, assignment_id, question in (("first@example.edu", 1, "3"), ("second@example.edu", 2, "7")):
            student = User(email=email, name=email, course="cs61a")
            db.session.add(student)
            db.session.flush()
            ticket = Ticket(user=student, status=TicketStatus.pending, assignment_id=assignment_id, location_id=1,
                            question=question, description="", course="cs61a")
            db.session.add(ticket)
            db.session.flush()
            tickets.append(ticket.id)
        db.session.commit()
    first, second = tickets

    site.log_in(*STAFF)
    site.visit(f"{COURSE}/tickets/{first}")
    site.button("Help").click()
    site.wait(lambda: "Being helped by you" in site.text())
    site.button("Resolve").click()
    site.wait(lambda: "Resolved by" in site.text())
    site.button("Next Ticket").click()
    site.wait(lambda: site.driver.current_url.rstrip("/").endswith(f"/tickets/{second}"))
    site.wait(lambda: site.driver.find_element(By.ID, "question").get_attribute("value") == "7")
    assert Select(site.driver.find_element(By.ID, "assignment_id")).first_selected_option.text == "Maps"

    assert "Update Assignment" not in site.text()
    assert site.console_errors() == []


def test_staff_see_a_timed_magic_word(site, app):
    site.visit(COURSE + "/")  # sets up the course's settings
    with app.app_context():
        settings = {"queue_magic_word_mode": "timed_numeric", "queue_magic_word_data": "0123456789abcdef:60:1000:9999"}
        for key, value in settings.items():
            ConfigEntry.query.filter_by(course="cs61a", key=key).one().value = value
        db.session.commit()
    site.log_in(*STAFF)
    site.visit(COURSE + "/")
    # right away, not after the first ten-second refresh
    site.wait(lambda: "Magic word:" in site.text(), timeout=5)
    assert site.console_errors() == []


def test_description_is_asked_for_when_required(site, app):
    """When the course requires a description, the Request button asks for one in a dialog."""
    site.visit(COURSE + "/")  # sets up the course's settings
    with app.app_context():
        ConfigEntry.query.filter_by(course="cs61a", key="description_required").one().value = "true"
        db.session.commit()
    site.log_in(*STUDENT)
    site.visit(COURSE + "/")
    Select(site.driver.find_element(By.ID, "assignment_id")).select_by_visible_text("Hog")
    Select(site.driver.find_element(By.ID, "location_id")).select_by_visible_text("Cory 247")
    site.driver.find_element(By.ID, "question").send_keys("3")
    site.button("Request").click()
    dialog = site.wait(lambda: site.driver.find_element(By.CSS_SELECTOR, "[role=dialog]"))
    box = dialog.find_element(By.ID, "description-box")
    # the dialog takes the focus, so it can be used from the keyboard
    site.wait(lambda: site.driver.execute_script("return arguments[0].contains(document.activeElement)", dialog))
    box.clear()
    box.send_keys("My tests time out")
    dialog.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    site.wait(lambda: "/tickets/" in site.driver.current_url)
    with app.app_context():
        assert Ticket.query.one().description == "My tests time out"
    assert site.console_errors() == []


def test_account_menu_signs_out(site):
    site.log_in(*STAFF)
    site.visit(COURSE + "/")
    menu = site.driver.find_element(By.ID, "account-menu")
    assert menu.get_attribute("aria-expanded") == "false"
    menu.click()
    site.wait(lambda: menu.get_attribute("aria-expanded") == "true")
    site.button("Log Out").click()
    # the landing page, signed out
    site.wait(lambda: site.driver.current_url == site.base_url + "/")
    site.visit(COURSE + "/")
    assert "Hi! Please sign in" in site.text()
