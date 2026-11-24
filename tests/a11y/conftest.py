"""The a11y audit's site, a course to audit, and its report of violations by rule. The
server and browser are shared with the end to end tests, in tests/browser.py."""

from collections import defaultdict

import pytest

from oh_queue import app
from oh_queue.models import (Assignment, Group, GroupAttendance, GroupAttendanceStatus, GroupStatus, Location,
                             Offering, Ticket, TicketStatus, User, db)
from tests.a11y.utils import REPORT_DIR
from tests.browser import live_site, slugify

# rule id -> pages that break it, printed at the end of the run
VIOLATIONS_BY_RULE = defaultdict(set)

COURSE = "/offerings/101"
# who signs in, through the development login: (email, name, is_staff)
STAFF = ("staff@example.edu", "Staff Member", True)
STUDENT = ("student@example.edu", "Student Person", False)


def seed():
    """CS 61A, with assignments, locations, and tickets in each state: the student's own,
    waiting; one the TA is helping; one resolved; and an active group. Returns the ids
    that page paths need."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        course = "cs61a"
        db.session.add(Offering(canvas_id=101, key=course, name="COMPSCI 61A - LEC 001", code="CS 61A"))
        # A course that was removed, which staff can import again on /offerings/new. (The
        # development login makes everyone a TA in every offering, hidden or not.)
        db.session.add(Offering(canvas_id=202, key="202", name="DATA C8 - LEC 001", code="DATA C8", hidden=True))
        hog = Assignment(name="Hog", course=course, visible=True)
        cory = Location(name="Cory 247", course=course, visible=True, online=False, link="")
        staff = User(email=STAFF[0], name=STAFF[1], is_staff=True, course=course)
        student = User(email=STUDENT[0], name=STUDENT[1], course=course)
        helped = User(email="helped@example.edu", name="Helped Student", course=course)
        grouped = User(email="grouped@example.edu", name="Grouped Student", course=course)
        db.session.add_all([hog, cory, staff, student, helped, grouped])
        db.session.flush()

        def ticket(user, status, question, helper=None):
            return Ticket(user=user, status=status, helper=helper, assignment=hog, location=cory,
                          question=question, description="I'm stuck on the second part.", course=course)

        mine = ticket(student, TicketStatus.pending, "3")
        assigned = ticket(helped, TicketStatus.assigned, "5", helper=staff)
        resolved = ticket(helped, TicketStatus.resolved, "Other", helper=staff)
        group = Group(question="7", description="Debugging together", assignment_id=hog.id, location_id=cory.id,
                      course=course, group_status=GroupStatus.active)
        db.session.add_all([mine, assigned, resolved, group])
        db.session.flush()
        db.session.add(GroupAttendance(group_id=group.id, user_id=grouped.id, course=course,
                                       group_attendance_status=GroupAttendanceStatus.present))
        db.session.commit()
        ids = {"mine": mine.id, "assigned": assigned.id, "resolved": resolved.id, "group": group.id,
               "staff": staff.id, "student": student.id}
        db.session.remove()
        return ids


class A11ySite:
    """The site, signed in as whoever a page needs, and the seeded course's ids."""

    def __init__(self, site, ids):
        self.site = site
        self.driver = site.driver
        self.base_url = site.base_url
        self.ids = ids
        self.user = None

    def visit(self, path, user=None):
        """Open a page and wait until it has loaded its data."""
        if user != self.user:
            self.driver.delete_all_cookies()
            if user is not None:
                self.site.log_in(*user)
            self.user = user
        self.driver.get(self.base_url + path)
        self.site.settle()
        return self.driver


@pytest.fixture(scope="session")
def a11y_site():
    """One browser and server, shared by every page's a11y audit, which only looks."""
    ids = seed()
    # a tall window keeps most of each page on screen, since axe skips the contrast of text off screen
    with live_site(window_size="1280,4000") as site:
        yield A11ySite(site, ids)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    site = item.funcargs.get("a11y_site") if hasattr(item, "funcargs") else None
    if report.when == "call" and report.failed and site is not None:
        screenshots = REPORT_DIR / "screenshots"
        screenshots.mkdir(parents=True, exist_ok=True)
        site.driver.save_screenshot(str(screenshots / f"{slugify(item.name)}.png"))


def pytest_terminal_summary(terminalreporter):
    if not VIOLATIONS_BY_RULE:
        return
    terminalreporter.section("accessibility violations by rule")
    for rule, pages in sorted(VIOLATIONS_BY_RULE.items()):
        terminalreporter.write_line(f"{rule} ({len(pages)} pages)")
        for page in sorted(pages):
            terminalreporter.write_line(f"  {page}")
