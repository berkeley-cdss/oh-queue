"""The Canvas API calls made when someone signs in."""

from canvasapi import Canvas
from canvasapi.course import Course
from flask import current_app

# What the app asks Canvas for at sign-in.
SCOPES = [
    "url:GET|/api/v1/users/:id",
    "url:GET|/api/v1/courses/:id",
    "url:GET|/api/v1/users/:user_id/courses",
    "url:GET|/api/v1/users/:user_id/profile",
    "url:GET|/api/v1/courses/:course_id/enrollments",
]


def _client(access_token: str) -> Canvas:
    return Canvas(current_app.config["CANVAS_SERVER_URL"], access_token)


def get_profile(user_id, access_token: str) -> dict:
    return _client(access_token).get_user(user_id).get_profile()


def get_course(course_id: int, access_token: str) -> Course:
    return _client(access_token).get_course(course_id)


def in_admin_override_course(user_id, access_token: str) -> bool:
    """Whether the user is in ADMIN_OVERRIDE_CANVAS_COURSE_ID, which makes
    them staff in every course."""
    override_id = current_app.config.get("ADMIN_OVERRIDE_CANVAS_COURSE_ID")
    if override_id is None:
        return False
    courses = _client(access_token).get_user(user_id).get_courses(
        enrollment_status="active", per_page=100
    )
    return any(c.id == override_id for c in courses)


def is_staff(course: Course, user_id) -> bool:
    """Whether the user is a TA or teacher in a Canvas course."""
    return any(
        e.type in ("TaEnrollment", "TeacherEnrollment")
        for e in course.get_enrollments(user_id=str(user_id))
    )
