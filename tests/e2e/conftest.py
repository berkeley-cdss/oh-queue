"""End to end tests: the app on a local server, used through headless Chrome as people
use it, as in sections. The server and browser are shared with the a11y audit, in
tests/browser.py. Run them with `pytest tests/e2e`, after `yarn build`."""

from pathlib import Path

import pytest

from oh_queue.models import Assignment, Location, Offering, db
from tests.browser import CANVAS_COURSE_ID, live_site, slugify

SCREENSHOTS = Path("e2e-screenshots")


@pytest.fixture(scope="session")
def live():
    with live_site() as site:
        yield site


@pytest.fixture()
def site(app, live):
    """The browser and server, with the test offering (tests/conftest.py), its
    assignments and locations, and no one signed in. The offering is the fake
    Canvas's course, so its seeded users are enrolled in it."""
    with app.app_context():
        Offering.query.filter_by(key="cs61a").one().canvas_id = CANVAS_COURSE_ID
        db.session.add_all([
            Assignment(name="Hog", course="cs61a", visible=True),
            Location(name="Cory 247", course="cs61a", visible=True, online=False, link=""),
        ])
        db.session.commit()
    live.driver.delete_all_cookies()
    live.console_errors()
    yield live
    live.remove_scripts()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    site = item.funcargs.get("site") if hasattr(item, "funcargs") else None
    if report.when == "call" and report.failed and site is not None:
        SCREENSHOTS.mkdir(exist_ok=True)
        site.driver.save_screenshot(str(SCREENSHOTS / f"{slugify(item.name)}.png"))
