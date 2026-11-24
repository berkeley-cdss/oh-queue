"""The users, courses and enrollments the fake Canvas knows, the same as in
sections' server/fake_canvas_data. Keyed by Canvas id, as a string."""

import json
import os

_DIR = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    with open(os.path.join(_DIR, name)) as f:
        return json.load(f)


FAKE_USERS = _load("fake_users.json")
FAKE_COURSES = _load("fake_courses.json")
# {user id: {course id: {"enrollments": [...]}}}
FAKE_ENROLLMENTS = _load("fake_enrollments.json")
