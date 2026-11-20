"""Which course the current request belongs to.

For now each deployment serves the one course set by COURSE_KEY and
CANVAS_COURSE_ID. Everything that needs the course asks this module, so
serving every course from one site only has to change how it decides.
"""

import re

from flask import current_app


def get_course() -> str:
    """The key stored in each row's ``course`` column, such as "cs61a"."""
    return current_app.config["COURSE_KEY"]


def get_canvas_course_id() -> int:
    return current_app.config["CANVAS_COURSE_ID"]


def format_coursecode(course: str) -> str:
    """A course key formatted for people, such as "CS 61A" for "cs61a"."""
    if course == "eecs189":
        return "CS 189/289A"
    if course == "cs189":
        return "CS 189 (CDSS)"
    m = re.match(r"([a-z]+)([0-9]+[a-z]?)", course)
    return (m.group(1) + " " + m.group(2)).upper() if m else course
