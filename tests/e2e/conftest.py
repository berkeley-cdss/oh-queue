"""The app on a local server, used through headless Chrome, as in sections' end to end
tests. They need Chrome and the frontend build (`yarn build`), so `pytest` leaves them
out (pytest.ini); run them with `pytest tests/e2e`."""

import json
import threading
import time
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.serving import make_server

from oh_queue.models import Assignment, Location, db
from oh_queue.vite import MANIFEST

SCREENSHOTS = Path("e2e-screenshots")


class Site:
    """One browser on one server."""

    def __init__(self, driver, base_url):
        self.driver = driver
        self.base_url = base_url
        # scripts that run on every page, added by watch_requests
        self.scripts = []

    def log_in(self, email, name, is_staff):
        """Sign in through the development login, as a TA or a student in every offering."""
        self.driver.delete_all_cookies()
        self.driver.get(f"{self.base_url}/testing-login/")
        for field, value in (("name", name), ("email", email)):
            element = self.driver.find_element(By.ID, field)
            element.clear()
            element.send_keys(value)
        if is_staff:
            self.driver.find_element(By.ID, "is_staff").click()
        self.driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
        self.wait(lambda: "/testing-login" not in self.driver.current_url)

    def visit(self, path):
        """Open a page and wait for the queue's first update from the server."""
        self.driver.get(self.base_url + path)
        self.wait(lambda: self.driver.find_element(By.ID, "content").text.strip())
        # The page asks the server for updates as soon as it loads; let them land.
        time.sleep(0.5)

    def wait(self, condition, timeout=10):
        """Wait until condition() is truthy, and return what it returned."""
        return WebDriverWait(self.driver, timeout, ignored_exceptions=[StaleElementReferenceException]) \
            .until(lambda _: condition())

    def button(self, text):
        xpath = f'//*[(self::button or self::a) and normalize-space()="{text}"]'
        return self.wait(lambda: next((e for e in self.driver.find_elements(By.XPATH, xpath) if e.is_displayed()),
                                      None))

    def watch_requests(self, fail=()):
        """From the next page opened: count the page's API requests by endpoint, in
        window.requests, and make those to the endpoints in fail fail, as if the
        server were unreachable."""
        # in a function, so its names don't become globals the page's scripts see
        script = """(() => {
            window.requests = {};
            const fail = %s;
            const fetch = window.fetch;
            window.fetch = (url, ...rest) => {
              const endpoint = String(url).split("/api/")[1];
              if (endpoint) {
                window.requests[endpoint] = (window.requests[endpoint] || 0) + 1;
                if (fail.includes(endpoint)) {
                  return Promise.reject(new TypeError("Failed to fetch"));
                }
              }
              return fetch(url, ...rest);
            };
        })();""" % json.dumps(list(fail))
        added = self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        self.scripts.append(added["identifier"])

    def requests(self, endpoint):
        return self.driver.execute_script("return window.requests[arguments[0]] || 0", endpoint)

    def text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    def console_errors(self):
        """The browser console's errors since the last call."""
        return [entry["message"] for entry in self.driver.get_log("browser") if entry["level"] == "SEVERE"]


@pytest.fixture(scope="session")
def live():
    from oh_queue import app

    if not Path(MANIFEST).exists():
        pytest.fail("The end to end tests need the frontend build: run `yarn build`.")

    server = make_server("localhost", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,1000")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    driver = webdriver.Chrome(options=options)
    try:
        yield Site(driver, f"http://localhost:{server.server_port}")
    finally:
        driver.quit()
        server.shutdown()
        thread.join()
        server.server_close()


@pytest.fixture()
def site(app, live):
    """The browser and server, with the test offering (tests/conftest.py), its
    assignments and locations, and no one signed in."""
    with app.app_context():
        db.session.add_all([
            Assignment(name="Hog", course="cs61a", visible=True),
            Location(name="Cory 247", course="cs61a", visible=True, online=False, link=""),
        ])
        db.session.commit()
    live.driver.delete_all_cookies()
    live.console_errors()
    yield live
    for script in live.scripts:
        live.driver.execute_cdp_cmd("Page.removeScriptToEvaluateOnNewDocument", {"identifier": script})
    live.scripts.clear()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    site = item.funcargs.get("site") if hasattr(item, "funcargs") else None
    if report.when == "call" and report.failed and site is not None:
        SCREENSHOTS.mkdir(exist_ok=True)
        site.driver.save_screenshot(str(SCREENSHOTS / f"{item.name}.png"))
