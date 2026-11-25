import datetime
import enum

from flask import g
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import literal, types

db = SQLAlchemy()


def utcnow():
    """The current time in UTC, without a time zone, as the database stores it."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class EnumType(db.TypeDecorator):
    impl = db.String(255)
    # The enum class is the only state, so queries using this type can be cached.
    cache_ok = True

    def __repr__(self):
        """Make alembic detect the right type"""
        return "db.String(length=255)"

    def __init__(self, enum_class):
        super(EnumType, self).__init__(self)
        self.enum_class = enum_class

    def process_bind_param(self, enum_value, dialect):
        return enum_value.name

    def process_result_value(self, name, dialect):
        # An outer join with no match (such as a ticket's group when it has
        # none) gives NULL for every column, even NOT NULL ones.
        return None if name is None else self.enum_class[name]

    @property
    def python_type(self):
        return self.enum_class


class StringSet(types.TypeDecorator):
    """A set of strings stored as comma-separated text, as in seating and sections."""

    impl = types.Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return ",".join(sorted(set(value or ())))

    def process_result_value(self, value, dialect):
        return set(value.split(",")) if value else set()


def set_contains(column, item: str):
    """SQL condition: the StringSet ``column`` contains ``item``."""
    # autoescape: keys like "cs61a_tutoring" contain "_", a LIKE wildcard.
    return (literal(",") + db.func.coalesce(column, "") + literal(",")).contains(f",{item},", autoescape=True)


def current_course_key():
    """The current offering's key, or None outside an offering's pages."""
    return g.offering.key if "offering" in g else None


# offerings.canvas_id is a 32-bit integer. Canvas gives a course on another
# shard a global ID (shard * 10**13 + local ID), which doesn't fit, so those
# courses are skipped, as in sections. Postgres refuses a query comparing the
# column with a bigger number.
MAX_OFFERING_CANVAS_ID = 2**31 - 1


def can_be_offering(canvas_id) -> bool:
    """Whether a Canvas course ID fits in offerings.canvas_id."""
    return int(canvas_id) <= MAX_OFFERING_CANVAS_ID


def start_month(start_at) -> str:
    """The year and month of an ISO 8601 term start, such as "2026-08", or ""."""
    return (start_at or "")[:7]


def newest_first_key(start_at, name):
    """Sorts courses newest term first, then by name (with reverse=True), as seating does."""
    return (start_at or "", name)


class Offering(db.Model):
    """One semester's bCourses course that has been set up in this app, as in
    seating and sections."""

    __tablename__ = "offerings"
    id = db.Column(db.Integer, primary_key=True)
    canvas_id = db.Column(db.Integer, unique=True, index=True, nullable=False)
    # The value of the `course` column on every other table. Offerings set up in
    # this app use str(canvas_id); offerings moved from the old per-course sites
    # keep their old key (e.g. "cs61a") so their existing rows don't need rewriting.
    key = db.Column(db.String(255), unique=True, nullable=False)
    # Canvas course name (e.g. "COMPSCI 61A - LEC 001") and code (e.g. "COMPSCI 61A").
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(255), nullable=True)
    # ISO 8601 start of the course's term, as in seating.
    start_at = db.Column(db.String(255), nullable=True)
    # Taken off the site by a course admin. The row stays, so importing the
    # course again brings it back under the same key, with its data, even
    # for a course linked to an old key like "cs61a".
    hidden = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    @classmethod
    def for_canvas_id(cls, canvas_id):
        """The offering for a Canvas course, or None. IDs too big for the
        column can't be one, and Postgres refuses to compare them with it."""
        return cls.query.filter_by(canvas_id=canvas_id).one_or_none() if can_be_offering(canvas_id) else None

    @property
    def display_name(self) -> str:
        return self.code or self.name

    @property
    def start_month(self) -> str:
        return start_month(self.start_at)

    def __repr__(self):
        return f"<Offering {self.name}>"


class User(db.Model, UserMixin):
    """One person, across all offerings, as in seating and sections.

    Roles are per offering, in sets of offering keys (the value of each row's
    `course` column), because offerings moved from the per-course sites keep
    their old keys. Inside an offering's pages, `is_staff` and `is_admin`
    answer for that offering.
    """

    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    # Set when the person first signs in; people moved from the per-course sites
    # who haven't signed in since don't have one.
    canvas_id = db.Column(db.String(255), unique=True, index=True, nullable=True)
    # Staff in every offering (member of ADMIN_OVERRIDE_CANVAS_COURSE_ID).
    is_global_admin = db.Column(db.Boolean, nullable=False, default=False)
    # Active Canvas courses at last sign-in, keyed by str(canvas course id):
    # {"name", "code", "start_at", "is_staff", "is_admin", "is_student"}.
    canvas_courses = db.Column(db.JSON, nullable=False, default=dict)
    staff_offerings = db.Column(StringSet, nullable=False, default=set)
    admin_offerings = db.Column(StringSet, nullable=False, default=set)
    student_offerings = db.Column(StringSet, nullable=False, default=set)

    # A staff member's default video call and shared document links (Online Setup).
    call_url = db.Column(db.String(255))
    doc_url = db.Column(db.String(255))

    def __init__(self, **kwargs):
        # Column defaults only apply on insert; set_role needs real sets before then.
        for field in ("staff_offerings", "admin_offerings", "student_offerings"):
            kwargs.setdefault(field, set())
        kwargs.setdefault("canvas_courses", {})
        kwargs.setdefault("is_global_admin", False)
        super().__init__(**kwargs)

    # Session ids are prefixed so cookies from before this table existed, which
    # hold the id of a different table's row, can't be mistaken for a user id.
    SESSION_ID_PREFIX = "user-"

    def get_id(self):
        return f"{self.SESSION_ID_PREFIX}{self.id}"

    @classmethod
    def parse_session_id(cls, session_id: str):
        prefix, _, user_id = session_id.partition(cls.SESSION_ID_PREFIX)
        return int(user_id) if not prefix and user_id.isdigit() else None

    @property
    def is_staff(self) -> bool:
        key = current_course_key()
        return key is not None and (self.is_global_admin or key in self.staff_offerings)

    @property
    def is_admin(self) -> bool:
        key = current_course_key()
        return key is not None and (self.is_global_admin or key in self.admin_offerings)

    def is_member_of(self, key: str) -> bool:
        return self.is_global_admin or key in self.staff_offerings or key in self.student_offerings

    def set_role(self, key: str, *, is_staff: bool, is_admin: bool = False):
        """Make this person staff (optionally admin) or a student in an offering."""
        if is_staff:
            self.staff_offerings = self.staff_offerings | {key}
            self.student_offerings = self.student_offerings - {key}
        else:
            self.student_offerings = self.student_offerings | {key}
            self.staff_offerings = self.staff_offerings - {key}
        if is_admin:
            self.admin_offerings = self.admin_offerings | {key}
        else:
            self.admin_offerings = self.admin_offerings - {key}

    def absorb(self, other: "User"):
        """Merge ``other`` (the same person under another email) into this user,
        moving their tickets, messages, groups, roles and links, then delete
        ``other``."""
        for model, column in USER_REFERENCES:
            model.query.filter(column == other.id).update({column: self.id}, synchronize_session="fetch")
        # One heartbeat per course: keep the newer.
        mine = {h.course: h for h in Heartbeat.query.filter_by(user_id=self.id)}
        for theirs in Heartbeat.query.filter_by(user_id=other.id).all():
            if theirs.course not in mine:
                theirs.user_id = self.id
            else:
                mine[theirs.course].time = max(mine[theirs.course].time, theirs.time)
                db.session.delete(theirs)
        self.staff_offerings = self.staff_offerings | other.staff_offerings
        self.admin_offerings = self.admin_offerings | other.admin_offerings
        self.student_offerings = (self.student_offerings | other.student_offerings) - self.staff_offerings
        self.call_url = self.call_url or other.call_url
        self.doc_url = self.doc_url or other.doc_url
        db.session.delete(other)
        db.session.flush()

    def canvas_roles_in(self, canvas_course_id: int):
        """``(is_staff, is_admin)`` in a Canvas course from the last sign-in, or
        None if not enrolled there."""
        info = (self.canvas_courses or {}).get(str(canvas_course_id))
        if info is None or not (info["is_staff"] or info["is_student"]):
            return None
        return info["is_staff"], info["is_admin"]

    @property
    def short_name(self):
        first_name = self.name.split()[0] if self.name.split() else ""
        if "@" in first_name:
            return first_name.rsplit("@")[0]
        return first_name


def with_email(email: str):
    """The person with this email, ignoring case (as the migration merged them)."""
    return User.query.filter(db.func.lower(User.email) == email.strip().lower()).one_or_none()


def in_course(key: str):
    """SQL condition: the person is staff or a student in offering ``key``."""
    return db.or_(set_contains(User.staff_offerings, key), set_contains(User.student_offerings, key))


def staff_in(key: str):
    """SQL condition: the person is staff in offering ``key``, as ``User.is_staff`` is."""
    return db.or_(User.is_global_admin.is_(True), set_contains(User.staff_offerings, key))


class Heartbeat(db.Model):
    """When someone last had a course's queue open, for the count of who's online
    and for closing groups everyone has left. Per course, since one person can
    have several courses' queues open at once."""

    __tablename__ = "heartbeat"
    __table_args__ = (db.UniqueConstraint("user_id", "course", name="uq_heartbeat_user_id_course"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    course = db.Column(db.String(255), nullable=False, index=True)
    time = db.Column(db.DateTime, nullable=False, index=True)

    user = db.relationship(User)

    @classmethod
    def beat(cls, user, course: str):
        heartbeat = cls.query.filter_by(user_id=user.id, course=course).one_or_none()
        if heartbeat is None:
            heartbeat = cls(user_id=user.id, course=course)
            db.session.add(heartbeat)
        heartbeat.time = utcnow()

    @classmethod
    def recent(cls, course: str, since: datetime.datetime):
        """Who had the course's queue open since ``since``."""
        return User.query.join(cls).filter(cls.course == course, cls.time > since)


class ConfigEntry(db.Model):
    """Represents persistent server-side configuration entries"""

    __tablename__ = "config_entries"
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text(), nullable=False)
    public = db.Column(db.Boolean, default=False)

    course = db.Column(db.String(255), nullable=False, index=True)


class Assignment(db.Model):
    """Represents a ticket's assignment."""

    __tablename__ = "assignment"
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=db.func.now())
    name = db.Column(db.String(255), nullable=False)
    visible = db.Column(db.Boolean, default=False)

    course = db.Column(db.String(255), nullable=False, index=True)


class Location(db.Model):
    """Represents a ticket's location."""

    __tablename__ = "location"
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=db.func.now())
    name = db.Column(db.String(255), nullable=False)
    online = db.Column(db.Boolean, nullable=False)
    link = db.Column(db.String(255), nullable=False)
    visible = db.Column(db.Boolean, default=False)

    course = db.Column(db.String(255), nullable=False, index=True)


TicketStatus = enum.Enum(
    "TicketStatus", "pending assigned resolved deleted juggled rerequested"
)

active_statuses = [
    TicketStatus.pending,
    TicketStatus.assigned,
    TicketStatus.juggled,
    TicketStatus.rerequested,
]


class Ticket(db.Model):
    """Represents an ticket in the queue. A student submits a ticket and receives
    help from a staff member.
    """

    __tablename__ = "ticket"
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=db.func.now(), index=True)
    updated = db.Column(db.DateTime, onupdate=db.func.now())
    status = db.Column(EnumType(TicketStatus), nullable=False, index=True)

    sort_key = db.Column(db.DateTime, default=db.func.now(), index=True)

    group = db.relationship("Group", back_populates="ticket", uselist=False)

    rerequest_threshold = db.Column(
        db.DateTime
    )  # time when student allowed to re-request help
    hold_time = db.Column(db.DateTime)  # time when student was put on hold
    rerequest_time = db.Column(db.DateTime)  # time when student re-requested help

    user_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    helper_id = db.Column(db.ForeignKey("users.id"), index=True)

    assignment_id = db.Column(
        db.ForeignKey("assignment.id"), nullable=False, index=True
    )
    location_id = db.Column(db.ForeignKey("location.id"), nullable=False, index=True)
    question = db.Column(db.String(255), nullable=False)

    description = db.Column(db.Text)

    user = db.relationship(User, foreign_keys=[user_id])
    helper = db.relationship(User, foreign_keys=[helper_id])
    assignment = db.relationship(Assignment, foreign_keys=[assignment_id])
    location = db.relationship(Location, foreign_keys=[location_id])

    course = db.Column(db.String(255), nullable=False, index=True)

    call_url = db.Column(db.String(255))
    doc_url = db.Column(db.String(255))

    @classmethod
    def for_user(cls, user):
        if user and user.is_authenticated:
            from oh_queue.offering import get_course

            return cls.query.filter(
                cls.user_id == user.id,
                cls.course == get_course(),
                cls.status.in_([TicketStatus.pending, TicketStatus.assigned]),
            ).one_or_none()

    @classmethod
    def by_status(cls, status=None):
        """Tickets in any of the states as status.
        @param status: Iterable containing TicketStatus values
        """
        if status is None:
            status = [TicketStatus.pending, TicketStatus.assigned]
        return cls.query.filter(cls.status.in_(status)).order_by(cls.created).all()


TicketEventType = enum.Enum(
    "TicketEventType",
    "create assign unassign resolve delete update juggle rerequest return_to hold_released message_sent shuffled unshuffled",
)


class TicketEvent(db.Model):
    """Represents an event that changes a ticket during its lifecycle."""

    __tablename__ = "ticket_event"
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.DateTime, default=db.func.now())
    event_type = db.Column(EnumType(TicketEventType), nullable=False)
    ticket_id = db.Column(db.ForeignKey("ticket.id"), nullable=False)
    user_id = db.Column(db.ForeignKey("users.id"), nullable=False)

    course = db.Column(db.String(255), nullable=False, index=True)

    ticket = db.relationship(Ticket)
    user = db.relationship(User)


GroupStatus = enum.Enum("GroupStatus", "active resolved")


class Group(db.Model):
    __tablename__ = "group"
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=db.func.now(), index=True)

    question = db.Column(db.String(255), nullable=False)
    description = db.Column(db.String(255), nullable=False, default="")

    assignment_id = db.Column(db.ForeignKey("assignment.id"), index=True)
    assignment = db.relationship(Assignment, foreign_keys=[assignment_id])

    location_id = db.Column(db.ForeignKey("location.id"), nullable=False, index=True)
    location = db.relationship(Location, foreign_keys=[location_id])

    ticket_id = db.Column(db.ForeignKey("ticket.id"), nullable=True, index=True)
    ticket = db.relationship(Ticket, back_populates="group", foreign_keys=[ticket_id])

    attendees = db.relationship(
        "GroupAttendance", back_populates="group", lazy="joined"
    )

    group_status = db.Column(
        EnumType(GroupStatus), nullable=False, default=GroupStatus.active
    )

    call_url = db.Column(db.String(255))
    doc_url = db.Column(db.String(255))

    course = db.Column(db.String(255), nullable=False, index=True)


GroupAttendanceStatus = enum.Enum("GroupAttendanceStatus", "present gone")


class GroupAttendance(db.Model):
    __tablename__ = "group_attendance"
    id = db.Column(db.Integer, primary_key=True)

    group_id = db.Column(db.ForeignKey("group.id"), nullable=False, index=True)
    group = db.relationship("Group", back_populates="attendees")

    user_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship(User, foreign_keys=[user_id], lazy="joined")

    group_attendance_status = db.Column(
        EnumType(GroupAttendanceStatus),
        nullable=False,
        default=GroupAttendanceStatus.present,
    )

    course = db.Column(db.String(255), nullable=False, index=True)


class ChatMessage(db.Model):
    __tablename__ = "chat_message"
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=db.func.now())

    body = db.Column(db.String(255), nullable=False, default="")

    user_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    user = db.relationship(User, foreign_keys=[user_id])

    ticket_id = db.Column(db.ForeignKey("ticket.id"), nullable=True, index=True)
    ticket = db.relationship("Ticket", backref=db.backref("messages", lazy="joined"))

    group_id = db.Column(db.ForeignKey("group.id"), nullable=True, index=True)
    group = db.relationship("Group", backref=db.backref("messages", lazy="joined"))

    course = db.Column(db.String(255), nullable=False, index=True)


# Every column holding a User's id, besides Heartbeat.user_id.
USER_REFERENCES = [
    (Ticket, Ticket.user_id),
    (Ticket, Ticket.helper_id),
    (TicketEvent, TicketEvent.user_id),
    (GroupAttendance, GroupAttendance.user_id),
    (ChatMessage, ChatMessage.user_id),
]
