"""
Runs axe on every page of the app, signed in as the kind of user who sees it, as
sections' and seating's tests/a11y/test_a11y_pages.py do.

Each page must meet WCAG 2.1 AA, which Berkeley requires, and also WCAG 2.2 AA and axe's
best-practice and Section 508 rules, which every page meets.
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from oh_queue import app
from tests.a11y.conftest import VIOLATIONS_BY_RULE
from tests.a11y.utils import COMPLETE_A11Y_STANDARDS, REQUIRED_A11Y_STANDARDS, format_violations, run_axe, \
    save_report
from tests.browser import COURSE, STAFF, STUDENT, SeededUser

SRC = Path(__file__).parents[2] / "src" / "components"


@dataclass
class Page:
    name: str
    # the Flask route that serves it; every course page is the React app's
    rule: str
    # its path, with {ids} of the seeded course (conftest.py)
    path: str
    user: SeededUser = None
    # the React app's route, for course pages: as in app.jsx, or "admin:" and the
    # route in admin_layout.jsx
    route: str = None
    # where the page lands, when visiting it redirects
    lands_on: str = None
    # whether it's one of the error pages (errors.py)
    error: bool = False


COURSE_RULE = "/offerings/<int:canvas_course_id>/<path:path>"
COURSE_INDEX = "/offerings/<int:canvas_course_id>/"

PAGES = [
    Page("landing", "/", "/"),
    Page("dev login", "/dev_login/", "/dev_login/"),
    Page("signed-out queue", COURSE_INDEX, f"{COURSE}/", route="/"),

    Page("student offerings", "/offerings", "/offerings", STUDENT),
    Page("student queue", COURSE_INDEX, f"{COURSE}/", STUDENT, route="/"),
    Page("student queue page", COURSE_RULE, f"{COURSE}/queue", STUDENT, route="/queue"),
    Page("student party", COURSE_RULE, f"{COURSE}/party", STUDENT, route="/party"),
    Page("student ticket", COURSE_RULE, f"{COURSE}/tickets/{{mine}}", STUDENT, route="/tickets/:id/*"),
    Page("student activity", COURSE_RULE, f"{COURSE}/activity_log", STUDENT, route="/activity_log/*",
         lands_on=f"{COURSE}/user/{{student}}"),
    Page("course not set up", COURSE_INDEX, "/offerings/999/", STUDENT, error=True),
    # the student is a TA in another course, which they can set up
    Page("add offerings", "/offerings/new", "/offerings/new", STUDENT),

    Page("offerings", "/offerings", "/offerings", STAFF),
    Page("queue", COURSE_INDEX, f"{COURSE}/", STAFF, route="/"),
    Page("party", COURSE_RULE, f"{COURSE}/party", STAFF, route="/party"),
    Page("online setup", COURSE_RULE, f"{COURSE}/online_setup", STAFF, route="/online_setup"),
    Page("ticket", COURSE_RULE, f"{COURSE}/tickets/{{assigned}}", STAFF, route="/tickets/:id/*"),
    Page("resolved ticket", COURSE_RULE, f"{COURSE}/tickets/{{resolved}}", STAFF, route="/tickets/:id/*"),
    Page("group", COURSE_RULE, f"{COURSE}/groups/{{group}}", STAFF, route="/groups/:id/*"),
    Page("activity log", COURSE_RULE, f"{COURSE}/activity_log", STAFF, route="/activity_log/*"),
    Page("user", COURSE_RULE, f"{COURSE}/user/{{student}}", STAFF, route="/user/:id/*"),
    Page("presence", COURSE_RULE, f"{COURSE}/presence", STAFF, route="/presence/*"),
    Page("error", COURSE_RULE, f"{COURSE}/error?message=Something+went+wrong", STAFF, route="/error/*"),
    Page("not found", COURSE_RULE, f"{COURSE}/no_such_page", STAFF, route="*"),
    Page("admin", COURSE_RULE, f"{COURSE}/admin", STAFF, route="/admin/*"),
    Page("admin general", COURSE_RULE, f"{COURSE}/admin", STAFF, route="admin:index"),
    Page("admin tickets", COURSE_RULE, f"{COURSE}/admin/tickets", STAFF, route="admin:tickets/*"),
    Page("admin party", COURSE_RULE, f"{COURSE}/admin/party", STAFF, route="admin:party/*"),
    Page("admin assignments", COURSE_RULE, f"{COURSE}/admin/assignments", STAFF, route="admin:assignments/*"),
    Page("admin locations", COURSE_RULE, f"{COURSE}/admin/locations", STAFF, route="admin:locations/*"),
    Page("admin online", COURSE_RULE, f"{COURSE}/admin/online", STAFF, route="admin:online/*"),
]

# GET routes that are not audited, and why
SKIPPED_ROUTES = {
    "/static/<path:filename>": "not a page",
    "/health": "not a page",
    "/login/": "redirects to bCourses, or to the dev login",
    "/authorized/": "redirects after signing in with bCourses",
}

# The error pages are titled with their status, e.g. "404 Not Found".
ERROR_TITLES = re.compile(r"\d{3} ")


def test_every_page_is_audited():
    """Every page has an audit: each Flask route, and each of the React app's routes."""
    get_rules = {rule.rule for rule in app.url_map.iter_rules() if "GET" in rule.methods}
    audited = {page.rule for page in PAGES}
    missing = get_rules - audited - set(SKIPPED_ROUTES)
    assert not missing, f"Add these to PAGES or SKIPPED_ROUTES in {__file__}: {sorted(missing)}"
    assert not audited & set(SKIPPED_ROUTES)

    routes = set(re.findall(r'<Route\s+path="([^"]+)"', (SRC / "app.jsx").read_text()))
    admin = (SRC / "admin_layout.jsx").read_text()
    routes |= {f"admin:{route}" for route in re.findall(r'<Route\s+path="([^"]+)"', admin)}
    if re.search(r"<Route\s+index\b", admin):
        routes.add("admin:index")
    missing = routes - {page.route for page in PAGES}
    assert not missing, f"Add pages for these routes to PAGES in {__file__}: {sorted(missing)}"


def _audit(a11y_site, page, standards, label):
    path = page.path.format(**a11y_site.ids)
    driver = a11y_site.visit(path, page.user)
    lands_on = (page.lands_on or page.path).format(**a11y_site.ids)
    assert driver.current_url.rstrip("/") == (a11y_site.base_url + lands_on).rstrip("/")
    assert bool(ERROR_TITLES.match(driver.title)) == page.error, driver.title
    # a course page that couldn't find what it shows
    if page.route != "*":
        assert "Page Not Found" not in driver.page_source
    assert "Not found" not in a11y_site.site.text()
    report = run_axe(driver, standards)
    save_report(f"{page.name} {label}", report)
    for violation in report["violations"]:
        VIOLATIONS_BY_RULE[f"{violation['id']} ({label})"].add(page.name)
    return report


@pytest.mark.parametrize("page", PAGES, ids=[page.name for page in PAGES])
def test_meets_wcag_21_aa(a11y_site, page):
    report = _audit(a11y_site, page, REQUIRED_A11Y_STANDARDS, "WCAG 2.1 AA")
    assert not report["violations"], "\n" + format_violations(report)


@pytest.mark.parametrize("page", PAGES, ids=[page.name for page in PAGES])
def test_meets_wcag_22_aa(a11y_site, page):
    report = _audit(a11y_site, page, COMPLETE_A11Y_STANDARDS, "WCAG 2.2 AA")
    assert not report["violations"], "\n" + format_violations(report)
