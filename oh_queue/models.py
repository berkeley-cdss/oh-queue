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


class User(db.Model, UserMixin):
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
            from oh_queue.course import get_course

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
