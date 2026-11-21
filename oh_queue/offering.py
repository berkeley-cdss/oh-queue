"""Which course the current request belongs to.

Each course's queue and API live under /offerings/<canvas course id>/ (see
views.py), as in seating and sections; load_offering resolves that ID to an
Offering row for the rest of the request.
"""

from flask import abort, g

from oh_queue.models import Offering

OFFERING_URL_PREFIX = "/offerings/<int:canvas_course_id>"


def load_offering(canvas_course_id: int):
    offering = Offering.for_canvas_id(canvas_course_id)
    if offering is None or offering.hidden:
        abort(404, "The queue isn't set up for this course yet. If this is unexpected, ask your course staff.")
    g.offering = offering


def current_offering() -> Offering:
    return g.offering


def in_offering() -> bool:
    return "offering" in g


def get_canvas_course_id() -> int:
    return g.offering.canvas_id


def get_course() -> str:
    """The key stored in each row's ``course`` column."""
    return g.offering.key


def get_course_name() -> str:
    return g.offering.display_name
