import datetime
import enum

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

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


# offerings.canvas_id is a 32-bit integer. Canvas gives a course on another
# shard a global ID (shard * 10**13 + local ID), which doesn't fit, so those
# courses are skipped, as in sections. Postgres refuses a query comparing the
# column with a bigger number.
MAX_OFFERING_CANVAS_ID = 2**31 - 1


def can_be_offering(canvas_id) -> bool:
    """Whether a Canvas course ID fits in offerings.canvas_id."""
    return int(canvas_id) <= MAX_OFFERING_CANVAS_ID


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
        return (self.start_at or "")[:7]

    def __repr__(self):
        return f"<Offering {self.name}>"


class Account(db.Model, UserMixin):
    """Someone signed in with Canvas, across all of their courses, as in sections.

    Flask-Login keeps the account's id in the session. Inside an offering, the
    login manager resolves it to that course's User row (see login.py), which
    holds what is per course: staff status, call and doc links, tickets.
    """

    __tablename__ = "account"
    id = db.Column(db.Integer, primary_key=True)
    canvas_id = db.Column(db.String(255), unique=True, index=True, nullable=False)
    email = db.Column(db.String(255), index=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    # Staff in every course (member of ADMIN_OVERRIDE_CANVAS_COURSE_ID).
    is_global_admin = db.Column(db.Boolean, nullable=False, default=False)
    # Active Canvas courses at last sign-in, keyed by str(canvas course id):
    # {"name", "code", "start_at", "is_staff", "is_admin", "is_student"}.
    canvas_courses = db.Column(db.JSON, nullable=False, default=dict)

    # Session ids are prefixed so cookies from the per-course sites, which hold
    # a User id, can't be mistaken for an account id.
    SESSION_ID_PREFIX = "account-"

    def get_id(self):
        return f"{self.SESSION_ID_PREFIX}{self.id}"

    @classmethod
    def parse_session_id(cls, session_id: str):
        prefix, _, account_id = session_id.partition(cls.SESSION_ID_PREFIX)
        return int(account_id) if not prefix and account_id.isdigit() else None

    def course_info(self, canvas_course_id: int):
        """The account's Canvas role details in a course, or None if not enrolled."""
        info = self.canvas_courses.get(str(canvas_course_id))
        if info is None or not (info["is_staff"] or info["is_student"]):
            return None
        return info

    def is_staff_in(self, canvas_course_id: int) -> bool:
        info = self.course_info(canvas_course_id)
        return self.is_global_admin or bool(info and info["is_staff"])

    def is_admin_in(self, canvas_course_id: int) -> bool:
        """Teachers and Lead TAs, who can take an offering off the site."""
        info = self.course_info(canvas_course_id)
        return self.is_global_admin or bool(info and info["is_admin"])


class User(db.Model, UserMixin):
    """Someone in one course: each course has its own row for a person."""

    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    created = db.Column(db.DateTime, default=db.func.now())
    email = db.Column(db.String(255), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    is_staff = db.Column(db.Boolean, default=False)
    # is_admin = db.Column(db.Boolean, default=False)

    course = db.Column(db.String(255), nullable=False, index=True)

    call_url = db.Column(db.String(255))
    doc_url = db.Column(db.String(255))
    heartbeat_time = db.Column(db.DateTime, default=db.func.now(), index=True)

    @property
    def short_name(self):
        first_name = self.name.split()[0] if self.name.split() else ""
        if "@" in first_name:
            return first_name.rsplit("@")[0]
        return first_name


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

    user_id = db.Column(db.ForeignKey("user.id"), nullable=False, index=True)
    helper_id = db.Column(db.ForeignKey("user.id"), index=True)

    assignment_id = db.Column(
        db.ForeignKey("assignment.id"), nullable=False, index=True
    )
    location_id = db.Column(db.ForeignKey("location.id"), nullable=False, index=True)
    question = db.Column(db.String(255), nullable=False)

    description = db.Column(db.Text)
    llm_tips = db.Column(db.Text)
    use_llm = db.Column(db.Boolean, nullable=False, default=False)
    student_help_type = db.Column(db.String(64))
    student_help_other = db.Column(db.Text)
    staff_help_type = db.Column(db.String(64))
    staff_help_other = db.Column(db.Text)
    llm_tips_influence = db.Column(db.String(64))

    user = db.relationship(User, foreign_keys=[user_id])
    helper = db.relationship(User, foreign_keys=[helper_id])
    assignment = db.relationship(Assignment, foreign_keys=[assignment_id])
    location = db.relationship(Location, foreign_keys=[location_id])

    course = db.Column(db.String(255), nullable=False, index=True)

    call_url = db.Column(db.String(255))
    doc_url = db.Column(db.String(255))
    use_llm = db.Column(db.Boolean, nullable=False, default=False)

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
    user_id = db.Column(db.ForeignKey("user.id"), nullable=False)

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
    use_llm = db.Column(db.Boolean, nullable=False, default=False)

    course = db.Column(db.String(255), nullable=False, index=True)


GroupAttendanceStatus = enum.Enum("GroupAttendanceStatus", "present gone")


class GroupAttendance(db.Model):
    __tablename__ = "group_attendance"
    id = db.Column(db.Integer, primary_key=True)

    group_id = db.Column(db.ForeignKey("group.id"), nullable=False, index=True)
    group = db.relationship("Group", back_populates="attendees")

    user_id = db.Column(db.ForeignKey("user.id"), nullable=False, index=True)
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

    user_id = db.Column(db.ForeignKey("user.id"), nullable=False, index=True)
    user = db.relationship(User, foreign_keys=[user_id])

    ticket_id = db.Column(db.ForeignKey("ticket.id"), nullable=True, index=True)
    ticket = db.relationship("Ticket", backref=db.backref("messages", lazy="joined"))

    group_id = db.Column(db.ForeignKey("group.id"), nullable=True, index=True)
    group = db.relationship("Group", backref=db.backref("messages", lazy="joined"))

    course = db.Column(db.String(255), nullable=False, index=True)
