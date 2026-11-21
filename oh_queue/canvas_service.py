"""The Canvas API calls made when someone signs in."""

from canvasapi import Canvas
from flask import current_app

from oh_queue.models import can_be_offering

# What the app asks Canvas for at sign-in.
SCOPES = [
    "url:GET|/api/v1/users/:id",
    "url:GET|/api/v1/users/:user_id/courses",
    "url:GET|/api/v1/users/:user_id/profile",
]

# Enrollment types as the user courses endpoint reports them.
STAFF_ENROLLMENT_TYPES = {"ta", "teacher"}


def _client(access_token: str) -> Canvas:
    return Canvas(current_app.config["CANVAS_SERVER_URL"], access_token)


def get_profile(user_id, access_token: str) -> dict:
    return _client(access_token).get_user(user_id).get_profile()


def _start_at(course):
    """The term's start, else the course's own start, else its creation, like seating."""
    term = getattr(course, "term", None) or {}
    return term.get("start_at") or getattr(course, "start_at", None) or getattr(course, "created_at", None)


def get_user_courses(user_id, access_token: str) -> dict:
    """The user's active Canvas courses and their role in each, as in sections.

    Returns ``{str(course id): {"name", "code", "start_at", "is_staff", "is_admin",
    "is_student"}}``. Staff are TAs and Teachers; admins are Teachers and Lead TAs.
    """
    courses = {}
    for c in _client(access_token).get_user(user_id).get_courses(
        enrollment_state="active", include=["term"], per_page=100
    ):
        enrollments = getattr(c, "enrollments", None) or []
        if not enrollments or not hasattr(c, "course_code"):
            continue  # courses the user can't see, or restricted by date
        if not can_be_offering(c.id):
            current_app.logger.info("Skipped Canvas course %s (%s): its ID is too big", c.id, c.name)
            continue
        types = {e["type"] for e in enrollments}
        roles = {e.get("role") for e in enrollments}
        courses[str(c.id)] = {
            "name": c.name,
            "code": c.course_code,
            "start_at": _start_at(c),
            "is_staff": bool(types & STAFF_ENROLLMENT_TYPES),
            "is_admin": "teacher" in types or "Lead TA" in roles,
            "is_student": "student" in types,
        }
    return courses
