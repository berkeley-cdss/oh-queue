"""The live server and headless Chrome that the end to end tests (tests/e2e) and the
a11y audit (tests/a11y) share, as in sections' tests/browser.py. Both need Chrome and
the frontend build (`yarn build`), so `pytest` leaves them out (pytest.ini)."""

import json
import re
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.common.exceptions import StaleElementReferenceException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from werkzeug.serving import make_server

from oh_queue.vite import MANIFEST

# Counts the page's requests in flight, so a test can wait for the course page's data
# to load. It runs before the page's own scripts, in a function so its names don't
# become globals the page's scripts see.
COUNT_FETCHES = """(() => {
  window.pendingFetches = 0;
  const fetch = window.fetch;
  window.fetch = (...args) => {
    window.pendingFetches++;
    return fetch(...args).finally(() => window.pendingFetches--);
  };
})();"""
LOADED = "return document.readyState === 'complete' && window.pendingFetches === 0"


def slugify(text):
    """text as a file name, for reports and screenshots."""
    return re.sub(r"[^\w.-]+", "-", text).strip("-")


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
        """Open a course page and wait for the queue's first update from the server."""
        self.driver.get(self.base_url + path)
        self.wait(lambda: self.driver.find_element(By.ID, "content").text.strip())
        # The page asks the server for updates as soon as it loads; let them land.
        time.sleep(0.5)

    def settle(self):
        """Wait until the page has loaded and its requests have finished."""
        self.wait(lambda: self.driver.execute_script(LOADED))

    def wait(self, condition, timeout=10):
        """Wait until condition() is truthy, and return what it returned."""
        return WebDriverWait(self.driver, timeout, ignored_exceptions=[StaleElementReferenceException]) \
            .until(lambda _: condition())

    def button(self, text):
        xpath = f'//*[(self::button or self::a) and normalize-space()="{text}"]'
        return self.wait(lambda: next((e for e in self.driver.find_elements(By.XPATH, xpath) if e.is_displayed()),
                                      None))

    def watch_requests(self, fail=None):
        """From the next page opened: count the page's API requests by endpoint, in
        window.requests, and make requests to the endpoints in fail, a dict of
        endpoint to how many of its first requests fail, fail as if the server were
        unreachable."""
        script = """(() => {
            window.requests = {};
            const fail = %s;
            const fetch = window.fetch;
            window.fetch = (url, ...rest) => {
              const endpoint = String(url).split("/api/")[1];
              if (endpoint) {
                window.requests[endpoint] = (window.requests[endpoint] || 0) + 1;
                if (window.requests[endpoint] <= (fail[endpoint] || 0)) {
                  return Promise.reject(new TypeError("Failed to fetch"));
                }
              }
              return fetch(url, ...rest);
            };
        })();""" % json.dumps(fail or {})
        self.scripts.append(self.add_script(script))

    def add_script(self, script):
        """Run script on every page opened from now on, before the page's own; returns its id."""
        return self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})["identifier"]

    def remove_scripts(self):
        """Stop running the scripts watch_requests added."""
        for script in self.scripts:
            self.driver.execute_cdp_cmd("Page.removeScriptToEvaluateOnNewDocument", {"identifier": script})
        self.scripts.clear()

    def requests(self, endpoint):
        return self.driver.execute_script("return window.requests[arguments[0]] || 0", endpoint)

    def text(self):
        return self.driver.find_element(By.TAG_NAME, "body").text

    def console_errors(self):
        """The browser console's errors since the last call."""
        return [entry["message"] for entry in self.driver.get_log("browser") if entry["level"] == "SEVERE"]


@contextmanager
def live_site(window_size="1280,1000"):
    """The app on a local server, with headless Chrome to visit it."""
    from oh_queue import app

    if not Path(MANIFEST).exists():
        pytest.fail("The browser tests need the frontend build: run `yarn build`.")

    server = make_server("localhost", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument(f"--window-size={window_size}")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    driver = webdriver.Chrome(options=options)
    try:
        site = Site(driver, f"http://localhost:{server.server_port}")
        site.add_script(COUNT_FETCHES)
        yield site
    finally:
        driver.quit()
        server.shutdown()
        thread.join()
        server.server_close()
