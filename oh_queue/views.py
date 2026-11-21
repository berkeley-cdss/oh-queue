import datetime
import functools
import random
import time
from operator import or_
from urllib.parse import urljoin, urlparse

from flask import Blueprint, g, jsonify, render_template, request, url_for
from flask_login import current_user
from oh_queue import app, db
from oh_queue.models import (
    Assignment,
    ChatMessage,
    ConfigEntry,
    Group,
    GroupAttendance,
    GroupAttendanceStatus,
    GroupStatus,
    Location,
    Ticket,
    TicketEvent,
    TicketEventType,
    TicketStatus,
    User,
    active_statuses,
    utcnow,
)
from sqlalchemy import desc
from sqlalchemy.orm import joinedload, selectinload
import requests

from oh_queue.offering import OFFERING_URL_PREFIX, get_course, get_course_name, load_offering

# Each course's queue page and API live under /offerings/<canvas course id>/.
bp = Blueprint("offering", __name__, url_prefix=OFFERING_URL_PREFIX)


@bp.url_value_preprocessor
def pull_offering(endpoint, values):
    load_offering(values.pop("canvas_course_id"))


@bp.url_defaults
def add_offering(endpoint, values):
    if "offering" in g:
        values.setdefault("canvas_course_id", g.offering.canvas_id)


def public_user_json(user):
    """Who someone is, for people who can't see their details."""
    return {
        "id": user.id,
        "name": user.name,
        "shortName": user.short_name,
        "isStaff": user.is_staff,
    }


def user_json(user):
    return {
        **public_user_json(user),
        "email": user.email,
        "call_url": user.call_url,
        "doc_url": user.doc_url,
    }


def message_json(message: ChatMessage):
    return {
        "user": user_json(message.user),
        "body": message.body,
        "created": message.created.isoformat(),
    }


def public_ticket_json(ticket):
    """Someone else's ticket, as the queue lists it: no student, description,
    chat, links or LLM tips. A field added here goes to everyone."""
    return {
        "id": ticket.id,
        "status": ticket.status.name,
        "user": None,
        "created": ticket.created.isoformat(),
        "sort_key": ticket.sort_key.isoformat(),
        "hold_time": ticket.hold_time and ticket.hold_time.isoformat(),
        "rerequest_time": ticket.rerequest_time and ticket.rerequest_time.isoformat(),
        "updated": ticket.updated and ticket.updated.isoformat(),
        "location_id": ticket.location_id,
        "assignment_id": ticket.assignment_id,
        "question": ticket.question,
        "helper": ticket.helper and public_user_json(ticket.helper),
        "group_id": ticket.group.id if ticket.group else None,
        "messages": [],
    }


def ticket_json(ticket):
    if not can_view_ticket(ticket):
        return public_ticket_json(ticket)
    return {
        **public_ticket_json(ticket),
        "user": user_json(ticket.user),
        "rerequest_threshold": ticket.rerequest_threshold
        and ticket.rerequest_threshold.isoformat(),
        "description": ticket.description,
        "helper": ticket.helper and user_json(ticket.helper),
        "call_url": ticket.call_url,
        "doc_url": ticket.doc_url,
        "messages": [message_json(message) for message in ticket.messages],
        "llm_tips": ticket.llm_tips,
        "use_llm": ticket.use_llm,
        "student_help_type": ticket.student_help_type,
        "student_help_other": ticket.student_help_other,
        "staff_help_type": ticket.staff_help_type,
        "staff_help_other": ticket.staff_help_other,
        "llm_tips_influence": ticket.llm_tips_influence,
    }


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).lower() in ["true", "1", "yes", "on"]


def llm_tips_enabled():
    entry = ConfigEntry.query.filter_by(
        key="enable_llm_features", course=get_course()
    ).one_or_none()
    return entry is not None and entry.value == "true"


LLM_HELP_TYPE_OPTIONS = {
    "conceptual",
    "debugging",
    "past_exams_studying",
    "other",
}

LLM_TIPS_INFLUENCE_OPTIONS = {
    "helpful",
    "helpful_minimal",
    "neutral",
    "not_helpful_but_accurate",
    "not_helpful_at_all",
}


def ensure_config_entry(key, value, public):
    entry = ConfigEntry.query.filter_by(key=key, course=get_course()).one_or_none()

    if entry is None:
        try:
            new_entry = ConfigEntry(key=key, value=value, public=public, course=get_course())
            db.session.add(new_entry)
            db.session.commit()  # Commit IMMEDIATELY
        except Exception:
            db.session.rollback()  # roll back and ignore the error


def build_llm_tips_payload(ticket):
    chat_log = [
        {
            "user": message.user.short_name if message.user else "Unknown",
            "body": message.body,
            "created": message.created.isoformat(),
        }
        for message in sorted(ticket.messages, key=lambda msg: msg.created)
    ]
    return {
        "assignment": ticket.assignment.name if ticket.assignment else "",
        "question": ticket.question,
        "location": ticket.location.name if ticket.location else "",
        "description": ticket.description or "",
        "chat": chat_log,
        "student_email": ticket.user.email if ticket.user else "",
    }


def request_llm_tips_if_enabled(ticket):
    if not llm_tips_enabled() or not ticket.use_llm:
        return
    endpoint = app.config.get("LLM_TIPS_ENDPOINT")
    auth_token = app.config.get("LLM_TIPS_AUTH_TOKEN")
    if not endpoint or not auth_token:
        app.logger.info(
            "LLM tips skipped for ticket %s; endpoint or auth token missing", ticket.id
        )
        return

    payload = build_llm_tips_payload(ticket)
    headers = {"Content-Type": "application/json", "Authorization": auth_token}
    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers=headers,
            timeout=(3.05, 60),
        )
        response.raise_for_status()
    except requests.exceptions.ConnectTimeout:
        app.logger.warning(
            "LLM tips request connect timeout for ticket %s", ticket.id
        )
        return
    except requests.exceptions.ReadTimeout:
        app.logger.warning("LLM tips request read timeout for ticket %s", ticket.id)
        return
    except requests.RequestException as exc:
        app.logger.warning(
            "LLM tips request failed for ticket %s: %s", ticket.id, exc, exc_info=True
        )
        return

    try:
        data = response.json()
    except ValueError:
        app.logger.warning(
            "LLM tips response not JSON for ticket %s (status %s)",
            ticket.id,
            response.status_code,
        )
        return

    tip_text = data.get("llm_tips") or data.get("tips") or data.get("Miloh")
    if not isinstance(tip_text, str) or not tip_text.strip():
        app.logger.info(
            "LLM tips response missing text for ticket %s: %s", ticket.id, data
        )
        return

    ticket.llm_tips = tip_text.strip()
    db.session.commit()
    emit_event(ticket, TicketEventType.update)


def assignment_json(assignment):
    return {"id": assignment.id, "name": assignment.name, "visible": assignment.visible}


def location_json(location):
    return {
        "id": location.id,
        "name": location.name,
        "visible": location.visible,
        "online": location.online,
        "link": location.link,
    }


def get_online_location():
    online_location = Location.query.filter_by(
        course=get_course(), name="Online"
    ).first()
    online_visible = (
        ConfigEntry.query.filter_by(key="online_active", course=get_course())
        .one()
        .value
        == "true"
    )
    if online_location is None:
        online_location = Location(
            name="Online",
            visible=online_visible,
            course=get_course(),
            online=True,
            link="",
        )
        db.session.add(online_location)
        db.session.commit()
    else:
        online_location.visible = online_visible
        db.session.commit()
    return online_location


def config_json():
    config = {}
    for config_entry in ConfigEntry.query.filter_by(course=get_course()).all():
        if config_entry.public:
            config[config_entry.key] = config_entry.value
    return config


def public_group_json(group: Group):
    """A group other students can join, as its card and page show it: no
    members' emails or links, and no group links or chat. A field added here
    goes to every signed-in student."""
    return {
        "id": group.id,
        "created": group.created.isoformat(),
        # The group's page lists its members for students deciding whether
        # to join.
        "attendees": [
            group_attendance_json(attendance, public_user_json)
            for attendance in group.attendees
            if attendance.group_attendance_status == GroupAttendanceStatus.present
        ],
        "location_id": group.location_id,
        "ticket_id": group.ticket_id,
        "assignment_id": group.assignment_id,
        "question": group.question,
        "description": group.description,
        "group_status": group.group_status.name,
        "messages": [],
    }


def group_json(group: Group):
    if not has_group_access(group):
        return public_group_json(group)
    return {
        **public_group_json(group),
        "attendees": [
            group_attendance_json(attendance, user_json)
            for attendance in group.attendees
            if attendance.group_attendance_status == GroupAttendanceStatus.present
        ],
        "call_url": group.call_url,
        "doc_url": group.doc_url,
        "messages": [message_json(message) for message in group.messages],
    }


def group_attendance_json(attendance: GroupAttendance, serialize_user=user_json):
    return {
        "id": attendance.id,
        "group_id": attendance.group_id,
        "group_attendance_status": attendance.group_attendance_status.name,
        "user": serialize_user(attendance.user),
    }


def add_response(event, payload):
    g.response_buffer.append([event, payload])


def emit_event(ticket, event_type):
    ticket_event = TicketEvent(
        event_type=event_type, ticket=ticket, user=current_user, course=get_course()
    )
    db.session.add(ticket_event)
    db.session.commit()
    add_response("event", {"type": event_type.name, "ticket": ticket_json(ticket)})


def emit_group_event(group, event_type):
    add_response("group_event", {"type": event_type, "group": group_json(group)})


def emit_state(attrs, entity=None):
    state = {}
    if "tickets" in attrs and not current_user.is_authenticated:
        # Signed-out visitors see how long the queue is, not what's on it.
        counts = dict(
            db.session.query(Ticket.status, db.func.count(Ticket.id))
            .filter(Ticket.status.in_(active_statuses), Ticket.course == get_course())
            .group_by(Ticket.status)
            .all()
        )
        state["tickets"] = []
        state["ticket_counts"] = {status.name: counts.get(status, 0) for status in active_statuses}
    elif "tickets" in attrs:
        tickets = (
            Ticket.query.filter(
                Ticket.status.in_(active_statuses), Ticket.course == get_course()
            )
            .options(joinedload(Ticket.user, innerjoin=True))
            .options(joinedload(Ticket.helper))
            # members too, for checking who can see each group ticket
            .options(joinedload(Ticket.group).selectinload(Group.attendees))
            .all()
        )
        if entity not in tickets and isinstance(entity, Ticket):
            if can_view_ticket(entity):
                tickets.append(entity)
        state["tickets"] = [ticket_json(ticket) for ticket in tickets]
    if "assignments" in attrs:
        assignments = Assignment.query.filter_by(course=get_course()).all()
        state["assignments"] = [
            assignment_json(assignment) for assignment in assignments
        ]
    if "locations" in attrs:
        locations = Location.query.filter(
            Location.course == get_course(), Location.name != "Online"
        ).all()
        state["locations"] = [location_json(location) for location in locations]
        state["locations"].append(location_json(get_online_location()))
    if "config" in attrs:
        state["config"] = config_json()
    if "groups" in attrs:
        # Signed-out visitors can't join a group, so they don't see who's in one.
        groups = []
        if current_user.is_authenticated:
            groups = (
                Group.query.filter(
                    Group.group_status == GroupStatus.active,
                    Group.course == get_course(),
                )
                .options(selectinload(Group.attendees))
                .all()
            )
        if entity not in groups and isinstance(entity, Group):
            if has_group_access(entity):
                groups.append(entity)
        state["groups"] = [group_json(group) for group in groups]
    if "current_user" in attrs:
        state["current_user"] = (
            user_json(current_user) if current_user.is_authenticated else None
        )
    if "presence" in attrs:
        out = dict(
            students=User.query.filter(
                User.heartbeat_time
                > utcnow() - datetime.timedelta(seconds=30),
                User.course == get_course(),
                User.is_staff == False,  # noqa: E712 (SQL, not Python)
            ).count()
        )
        active_staff = {
            (t.helper.email, t.helper.name)
            for t in Ticket.query.filter(
                Ticket.status.in_(active_statuses),
                Ticket.helper_id.isnot(None),
                Ticket.course == get_course(),
            ).all()
        }
        active_staff |= {
            (user.email, user.name)
            for user in User.query.filter(
                User.heartbeat_time
                > utcnow() - datetime.timedelta(seconds=30),
                User.course == get_course(),
                User.is_staff == True,  # noqa: E712 (SQL, not Python)
            ).all()
        }
        out["staff"] = len(active_staff)
        # Only staff see who's online.
        if current_user.is_authenticated and current_user.is_staff:
            out["staff_list"] = list(active_staff)
        state["presence"] = out

    add_response("state", state)


def init_config():
    db.session.add(
        ConfigEntry(
            key="welcome",
            value="Welcome to the OH Queue!",
            public=True,
            course=get_course(),
        )
    )
    db.session.add(
        ConfigEntry(key="is_queue_open", value="true", public=True, course=get_course())
    )
    db.session.add(
        ConfigEntry(
            key="description_required", value="false", public=True, course=get_course()
        )
    )
    db.session.add(
        ConfigEntry(
            key="queue_magic_word_mode", value="none", public=True, course=get_course()
        )
    )
    db.session.add(
        ConfigEntry(
            key="queue_magic_word_data", value="", public=False, course=get_course()
        )
    )
    db.session.add(
        ConfigEntry(key="juggling_delay", value="5", public=True, course=get_course())
    )
    db.session.add(
        ConfigEntry(key="ticket_prompt", value="", public=True, course=get_course())
    )
    db.session.add(
        ConfigEntry(
            key="online_active", value="false", public=True, course=get_course()
        )
    )
    db.session.add(
        ConfigEntry(
            key="students_set_online_link",
            value="false",
            public=True,
            course=get_course(),
        )
    )
    db.session.add(
        ConfigEntry(
            key="students_set_online_doc",
            value="false",
            public=True,
            course=get_course(),
        )
    )
    db.session.add(
        ConfigEntry(
            key="party_enabled", value="false", public=True, course=get_course()
        )
    )
    db.session.add(
        ConfigEntry(
            key="allow_private_party_tickets",
            value="true",
            public=True,
            course=get_course(),
        )
    )
    db.session.add(
        ConfigEntry(key="party_name", value="Party", public=True, course=get_course())
    )
    db.session.add(
        ConfigEntry(
            key="default_description", value="", public=True, course=get_course()
        )
    )
    db.session.add(
        ConfigEntry(key="show_presence", value="true", public=True, course=get_course())
    )
    db.session.add(
        ConfigEntry(
            key="enable_shuffle", value="false", public=True, course=get_course()
        )
    )
    db.session.add(
        ConfigEntry(
            key="send_ticket_notifications",
            value="true",
            public=True,
            course=get_course(),
        )
    )
    db.session.add(
        ConfigEntry(
            key="enable_llm_features",
            value="false",
            public=True,
            course=get_course(),
        )
    )
    db.session.commit()


# We run a React app, so serve index.html on all of a course's pages.
@bp.route("/")
@bp.route("/<path:path>")
def index(*args, **kwargs):
    check = db.session.query(ConfigEntry).filter_by(course=get_course()).first()
    if not check:
        init_config()
    ensure_config_entry("enable_llm_features", "false", True)
    db.session.commit()

    return render_template(
        "index.html",
        course_name=get_course_name(),
        # Where the course's pages and API are, for the React app.
        base_path=url_for("offering.index").rstrip("/"),
    )


@app.before_request
def initialize_response_buffer():
    g.response_buffer = []


def api(endpoint):
    def decorator(f):
        @functools.wraps(f)
        def handler():
            args = request.json
            resp = f() if args == {} else f(args)
            return jsonify({"action": resp, "updates": g.response_buffer})

        bp.add_url_rule(
            "/api/{}".format(endpoint), f.__name__, handler, methods=["POST"]
        )

        return f

    return decorator


def page_path(ticket_id=None, group_id=None):
    """A page of the course, as the React app's router names it: relative to
    the course's /offerings/<canvas course id>."""
    if ticket_id is not None:
        return f"/tickets/{ticket_id}/"
    if group_id is not None:
        return f"/groups/{group_id}/"
    return "/"


def socket_error(message, category="danger", ticket_id=None):
    return {
        "messages": [{"category": category, "text": message}],
        "redirect": page_path(ticket_id=ticket_id),
    }


def socket_redirect(**kwargs):
    return {"redirect": page_path(**kwargs)}


def socket_unauthorized():
    return socket_error("You don't have permission to do that")


def logged_in(f):
    @functools.wraps(f)
    def wrapper(*args, **kwds):
        if not current_user.is_authenticated and current_user.course == get_course():
            return socket_unauthorized()
        return f(*args, **kwds)

    return wrapper


def is_staff(f):
    @functools.wraps(f)
    def wrapper(*args, **kwds):
        if not (
            current_user.is_authenticated
            and current_user.is_staff
            and current_user.course == get_course()
        ):
            return socket_unauthorized()
        return f(*args, **kwds)

    return wrapper


def can_view_ticket(ticket: Ticket):
    """Whether to send the ticket in full: anyone who can change it, and its
    own student even after they leave its group."""
    return has_ticket_access(ticket) or (
        current_user.is_authenticated and ticket.user_id == current_user.id
    )


def has_ticket_access(ticket: Ticket):
    if not current_user.is_authenticated or not ticket:
        return False
    group = ticket.group
    if group:
        if not (current_user.is_staff or is_member_of(group)):
            return False
    elif not (current_user.is_staff or ticket.user.id == current_user.id):
        return False
    return True


def requires_ticket_access(f):
    @functools.wraps(f)
    def wrapper(*args, **kwds):
        data = args[0]
        ticket_id = data.get("id")
        if not ticket_id:
            return socket_error("Invalid ticket ID")
        ticket = Ticket.query.filter_by(id=ticket_id, course=get_course()).one_or_none()
        if not has_ticket_access(ticket):
            return socket_unauthorized()
        kwds["ticket"] = ticket
        return f(*args, **kwds)

    return wrapper


def has_group_access(group: Group):
    if not current_user.is_authenticated:
        return False
    if not group:
        return False
    if not (current_user.is_staff or is_member_of(group)):
        return False
    return True


def requires_group_access(f):
    @functools.wraps(f)
    def wrapper(*args, **kwds):
        data = args[0]
        group_id = data.get("id")
        if not group_id:
            return socket_error("Invalid group ID")
        group = Group.query.filter_by(id=group_id, course=get_course()).one_or_none()
        if not has_group_access(group):
            return socket_unauthorized()
        kwds["group"] = group
        return f(*args, **kwds)

    return wrapper


@api("connect")
def connect(data=None):
    if not current_user.is_authenticated:
        pass

    current_user.heartbeat_time = utcnow()

    entity_type = None

    if data:
        # The page's URL, such as /offerings/<canvas course id>/tickets/<id>/.
        url = data["url"]
        path = urlparse(url).path
        path = path.strip("/")
        parts = path.split("/")
        if len(parts) >= 2 and parts[-1].isdigit():
            entity_type = parts[-2]
            entity_id = int(parts[-1])

    if entity_type == "tickets":
        entity = Ticket.query.filter_by(course=get_course(), id=entity_id).one_or_none()
    elif entity_type == "groups":
        entity = Group.query.filter_by(course=get_course(), id=entity_id).one_or_none()
    else:
        entity = None

    emit_state(
        [
            "tickets",
            "assignments",
            "groups",
            "locations",
            "current_user",
            "config",
            "presence",
        ],
        entity,
    )


def get_magic_word(mode=None, data=None, time_offset=0):
    if mode is None:
        mode = (
            ConfigEntry.query.filter_by(
                course=get_course(), key="queue_magic_word_mode"
            )
            .one()
            .value
        )
    if mode == "none":
        return None

    if data is None:
        data = (
            ConfigEntry.query.filter_by(
                course=get_course(), key="queue_magic_word_data"
            )
            .one()
            .value
        )
    if mode == "text":
        return data
    if mode == "timed_numeric":
        # We don't need fancy ultra-secure stuff here
        # A basic server-side time-based, seeded RNG is enough
        # Seed data should be in the form 'a:b:c:d', where:
        # a: 8-byte seed (in hexadecimal)
        # b: Downsampling interval (in seconds)
        # c: Minimum generated number (in unsigned decimal)
        # d: Maximum generated number (in unsigned decimal)
        data = data.split(":")
        # Downsample time to allow for temporal leeway
        rand = random.Random()
        timestamp = time.time() // int(data[1])
        # Seeded RNG
        rand.seed("{}.{}".format(timestamp + time_offset, data[0]))
        return str(rand.randint(int(data[2]), int(data[3]))).zfill(len(data[3]))
    raise Exception("Unrecognized queue magic word mode")


def check_magic_word(magic_word):
    mode = (
        ConfigEntry.query.filter_by(course=get_course(), key="queue_magic_word_mode")
        .one()
        .value
    )
    if mode == "none":
        return True
    data = (
        ConfigEntry.query.filter_by(course=get_course(), key="queue_magic_word_data")
        .one()
        .value
    )
    if mode == "timed_numeric":
        # Allow for temporal leeway from lagging clients/humans
        for offset in (0, -1, 1):
            if get_magic_word(mode, data, time_offset=offset) == magic_word:
                return True
        return False
    return get_magic_word(mode, data) == magic_word


@api("refresh_magic_word")
@is_staff
def refresh_magic_word():
    return {"magic_word": get_magic_word()}


@api("create")
@logged_in
def create(form):
    """Stores a new ticket to the persistent database, and emits it to all
    connected clients.
    """
    is_open = (
        ConfigEntry.query.filter_by(course=get_course(), key="is_queue_open")
        .one()
        .value
        == "true"
    )
    party_enabled = (
        ConfigEntry.query.filter_by(course=get_course(), key="party_enabled")
        .one()
        .value
        == "true"
    )
    private_party_tickets_allowed = (
        ConfigEntry.query.filter_by(
            course=get_course(), key="allow_private_party_tickets"
        )
        .one()
        .value
        == "true"
    )
    if not is_open or (party_enabled and not private_party_tickets_allowed):
        return socket_error("The queue is closed", category="warning")
    if not check_magic_word(form.get("magic_word")):
        return socket_error("Invalid magic_word", category="warning")
    my_ticket = Ticket.for_user(current_user)
    if my_ticket:
        return socket_error(
            "You are already on the queue",
            category="warning",
            ticket_id=my_ticket.id,
        )
    assignment_id = form.get("assignment_id")
    location_id = form.get("location_id")
    question = form.get("question")
    description = form.get("description") or (
        ConfigEntry.query.filter_by(course=get_course(), key="default_description")
        .one()
        .value
    )

    call_link = form.get("call-link", "")
    doc_link = form.get("doc-link", "")
    use_llm = parse_bool(form.get("use_llm")) if llm_tips_enabled() else False

    location = Location.query.filter_by(
        course=get_course(), id=location_id
    ).one_or_none()
    if not location:
        return socket_error(
            "Unknown location (id: {})".format(location_id), category="warning"
        )

    call_link = process_call_link(call_link, location)

    if doc_link:
        doc_link = urljoin("https://", doc_link)

    # Create a new ticket and add it to persistent storage
    if assignment_id is None or location_id is None or not question:
        return socket_error("You must fill out all the fields", category="warning")

    assignment = Assignment.query.filter_by(
        course=get_course(), id=assignment_id
    ).one_or_none()
    if not assignment:
        return socket_error(
            "Unknown assignment (id: {})".format(assignment_id), category="warning"
        )

    ticket = Ticket(
        status=TicketStatus.pending,
        user=current_user,
        assignment=assignment,
        location=location,
        question=question,
        description=description,
        course=get_course(),
        call_url=call_link,
        doc_url=doc_link,
        use_llm=use_llm,
    )

    db.session.add(ticket)
    db.session.commit()

    emit_event(ticket, TicketEventType.create)
    request_llm_tips_if_enabled(ticket)
    return socket_redirect(ticket_id=ticket.id)


def get_tickets(ticket_ids, lock=False):
    query = Ticket.query.filter(
        Ticket.id.in_(ticket_ids), Ticket.course == get_course()
    )
    if lock:
        # Only the tickets: Postgres can't lock the chat messages that are
        # outer-joined onto them.
        query = query.with_for_update(of=Ticket)
    return query.all()


def get_next_ticket(location=None):
    """Return the user's first assigned but unresolved ticket.
    If none exist, return the first pending student re-request.
    If none exist, return to the first unassigned ticket.

    If a location is passed in, only returns a next ticket from
    provided location.
    """
    ticket = Ticket.query.filter(
        Ticket.helper_id == current_user.id,
        Ticket.status == TicketStatus.assigned,
        Ticket.course == get_course(),
    ).first()
    if not ticket:
        ticket = Ticket.query.filter(
            Ticket.status == TicketStatus.rerequested,
            Ticket.helper_id == current_user.id,
            Ticket.course == get_course(),
        ).order_by(Ticket.sort_key)
        ticket = ticket.first()
    if not ticket:
        ticket = Ticket.query.filter(
            Ticket.status == TicketStatus.rerequested,
            Ticket.helper_id.is_(None),
            Ticket.course == get_course(),
        ).order_by(Ticket.sort_key)
        ticket = ticket.first()
    if not ticket:
        ticket = Ticket.query.filter(
            Ticket.status == TicketStatus.pending, Ticket.course == get_course()
        ).order_by(Ticket.sort_key)
        if location:
            ticket = ticket.filter(Ticket.location == location)
        ticket = ticket.first()
    if ticket:
        return socket_redirect(ticket_id=ticket.id)
    else:
        return socket_redirect()


@api("next")
@is_staff
def next_ticket(ticket_ids):
    return get_next_ticket()


def is_member_of(group):
    return any(
        attendance.user_id == current_user.id
        for attendance in group.attendees
        if attendance.group_attendance_status == GroupAttendanceStatus.present
    )


@api("delete")
@logged_in
def delete(ticket_ids):
    tickets = get_tickets(ticket_ids)
    for ticket in tickets:
        ticket_group = ticket.group
        if not (
            current_user.is_staff
            or ticket.user.id == current_user.id
            or ticket_group
            and is_member_of(ticket_group)
        ):
            return socket_unauthorized()
        ticket.status = TicketStatus.deleted
        emit_event(ticket, TicketEventType.delete)
    db.session.commit()


@api("resolve")
@logged_in
def resolve(data):
    """Gets ticket_ids and an optional argument 'local'.
    Resolves all ticket_ids. If 'local' is set, then
    will only return a next ticket from the same location
    where the last ticket was resolved from.
    """
    ticket_ids = data.get("ticket_ids")
    local = data.get("local", False)
    location = None
    tickets = get_tickets(ticket_ids)
    for ticket in tickets:
        if not (current_user.is_staff or ticket.user.id == current_user.id):
            return socket_unauthorized()
        llm_feedback_required = (
            llm_tips_enabled()
            and ticket.use_llm
            and isinstance(ticket.llm_tips, str)
            and ticket.llm_tips.strip()
        )
        if llm_feedback_required:
            is_staff = current_user.is_staff
            is_student = current_user.id == ticket.user.id
            staff_help_type = data.get("staff_help_type")
            staff_help_other = data.get("staff_help_other")
            llm_tips_influence = data.get("llm_tips_influence")
            student_help_type = data.get("student_help_type")
            student_help_other = data.get("student_help_other")

            if is_staff:
                if staff_help_type not in LLM_HELP_TYPE_OPTIONS:
                    return socket_error(
                        "Please answer what you helped the student with.",
                        category="warning",
                        ticket_id=ticket.id,
                    )
                if (
                    staff_help_type == "other"
                    and (not staff_help_other or not staff_help_other.strip())
                ):
                    return socket_error(
                        "Please describe what you helped the student with.",
                        category="warning",
                        ticket_id=ticket.id,
                    )
                if llm_tips_influence not in LLM_TIPS_INFLUENCE_OPTIONS:
                    return socket_error(
                        "Please answer how the LLM tips influenced your approach.",
                        category="warning",
                        ticket_id=ticket.id,
                    )
                ticket.staff_help_type = staff_help_type
                ticket.staff_help_other = (
                    staff_help_other.strip() if staff_help_other else None
                )
                ticket.llm_tips_influence = llm_tips_influence

            if is_student and ticket.helper_id:
                if student_help_type:
                    if student_help_type not in LLM_HELP_TYPE_OPTIONS:
                        return socket_error(
                            "Please select a valid option for what staff helped with.",
                            category="warning",
                            ticket_id=ticket.id,
                        )
                    if (
                        student_help_type == "other"
                        and (not student_help_other or not student_help_other.strip())
                    ):
                        return socket_error(
                            "Please describe what staff helped with.",
                            category="warning",
                            ticket_id=ticket.id,
                        )
                    ticket.student_help_type = student_help_type
                    ticket.student_help_other = (
                        student_help_other.strip() if student_help_other else None
                    )
        ticket.status = TicketStatus.resolved
        if local:
            location = ticket.location
        emit_event(ticket, TicketEventType.resolve)
    db.session.commit()
    return get_next_ticket(location)


@api("juggle")
@is_staff
def juggle(data):
    """
    Gets ticket_ids and places them all on the juggle queue for the corresponding staff member
    """
    ticket_ids = data.get("ticket_ids")
    tickets = get_tickets(ticket_ids)
    location = None
    for ticket in tickets:
        ticket.status = TicketStatus.juggled
        ticket.hold_time = utcnow()
        ticket.rerequest_threshold = ticket.hold_time + datetime.timedelta(
            minutes=int(
                ConfigEntry.query.filter_by(course=get_course(), key="juggling_delay")
                .one()
                .value
            )
        )
        location = ticket.location
        emit_event(ticket, TicketEventType.juggle)
    db.session.commit()
    return get_next_ticket(location)


@api("assign")
@is_staff
def assign(ticket_ids):
    tickets = get_tickets(ticket_ids, True)

    for ticket in tickets:

        if ticket.status == TicketStatus.assigned and ticket.helper_id != current_user.id:
            return {
                "messages": [{
                    "category": "warning",
                    "text": "This ticket has already been assigned to another staff member.",
                    "ttl": 3000,
                }],
                "redirect": "/",
            }

        ticket.status = TicketStatus.assigned
        ticket.helper_id = current_user.id
        emit_event(ticket, TicketEventType.assign)
    db.session.commit()


@api("return_to")
@is_staff
def return_to(ticket_ids):
    tickets = get_tickets(ticket_ids, True)
    for ticket in tickets:
        ticket.status = TicketStatus.assigned

        ticket.helper_id = current_user.id
        emit_event(ticket, TicketEventType.return_to)

    db.session.commit()


@api("rerequest")
@logged_in
def rerequest(data):
    ticket_ids = data.get("ticket_ids")
    tickets = get_tickets(ticket_ids)
    for ticket in tickets:
        if not ticket.user.id == current_user.id:
            return socket_unauthorized()

        # Only juggled tickets have a threshold, and only after it passes.
        if ticket.rerequest_threshold is None or ticket.rerequest_threshold > utcnow():
            return socket_unauthorized()

        ticket.status = TicketStatus.rerequested
        ticket.rerequest_time = utcnow()

        emit_event(ticket, TicketEventType.rerequest)

    db.session.commit()


@api("cancel_rerequest")
@logged_in
def cancel_rerequest(data):
    ticket_ids = data.get("ticket_ids")
    tickets = get_tickets(ticket_ids)
    for ticket in tickets:
        if not ticket.user.id == current_user.id:
            return socket_unauthorized()

        ticket.status = TicketStatus.juggled
        emit_event(ticket, TicketEventType.juggle)

    db.session.commit()


@api("release_holds")
@is_staff
def release_holds(data):
    ticket_ids = data.get("ticket_ids")
    to_me = data.get("to_me")
    tickets = get_tickets(ticket_ids)
    for ticket in tickets:
        if ticket.status in [TicketStatus.juggled, TicketStatus.rerequested]:
            ticket.helper_id = current_user.id if to_me else None
            emit_event(ticket, TicketEventType.hold_released)
    db.session.commit()

    return socket_redirect()


@api("unassign")
@is_staff
def unassign(ticket_ids):
    tickets = get_tickets(ticket_ids)
    for ticket in tickets:
        ticket.status = TicketStatus.pending
        ticket.helper_id = None
        emit_event(ticket, TicketEventType.unassign)
    db.session.commit()


@api("shuffle_tickets")
@is_staff
def shuffle_tickets(ticket_ids):
    tickets = get_tickets(ticket_ids)
    ticket_sort_keys = [ticket.sort_key for ticket in tickets]
    random.shuffle(ticket_sort_keys)
    for ticket, sort_key in zip(tickets, ticket_sort_keys):
        ticket.sort_key = sort_key
        emit_event(ticket, TicketEventType.shuffled)
    db.session.commit()


@api("unshuffle_tickets")
@is_staff
def unshuffle_tickets(ticket_ids):
    tickets = get_tickets(ticket_ids)
    for ticket in tickets:
        ticket.sort_key = ticket.created
        emit_event(ticket, TicketEventType.unshuffled)
    db.session.commit()


@api("load_ticket")
@is_staff
def load_ticket(ticket_id):
    if not ticket_id:
        return socket_error("Invalid ticket ID")
    ticket = Ticket.query.filter_by(course=get_course(), id=ticket_id).one_or_none()
    if ticket:
        return ticket_json(ticket)


def apply_ticket_update(data, ticket=None):
    if not ticket:
        ticket_id = data["id"]
        ticket = Ticket.query.filter_by(id=ticket_id, course=get_course()).one()
    if "description" in data:
        ticket.description = data["description"]
    if "location_id" in data:
        ticket.location = Location.query.filter_by(
            course=get_course(), id=data["location_id"]
        ).one()
    if "assignment_id" in data:
        ticket.assignment = Assignment.query.filter_by(
            course=get_course(), id=data["assignment_id"]
        ).one()
    if "question" in data:
        ticket.question = data["question"]
    if current_user.is_staff:
        if "sort_key" in data:
            ticket.sort_key = data["sort_key"]


@api("update_ticket")
@requires_ticket_access
def update_ticket(data, ticket):
    apply_ticket_update(data, ticket)
    db.session.commit()
    emit_event(ticket, TicketEventType.update)
    return ticket_json(ticket)


@api("update_tickets")
@is_staff
def update_tickets(arr):
    ticket_ids = [data["id"] for data in arr]
    tickets = Ticket.query.filter(
        Ticket.id.in_(ticket_ids), Ticket.course == get_course()
    ).all()
    ticket_dict = {ticket.id: ticket for ticket in tickets}
    for data in arr:
        apply_ticket_update(data, ticket_dict[data["id"]])
    db.session.commit()
    return emit_state(["tickets"])


@api("add_assignment")
@is_staff
def add_assignment(data):
    name = data["name"]
    assignment = Assignment(name=name, course=get_course())
    db.session.add(assignment)
    db.session.commit()

    emit_state(["assignments"])
    db.session.refresh(assignment)
    return assignment_json(assignment)


@api("update_assignment")
@is_staff
def update_assignment(data):
    assignment = Assignment.query.filter_by(course=get_course(), id=data["id"]).one()
    if "name" in data:
        assignment.name = data["name"]
    if "visible" in data:
        assignment.visible = data["visible"]
    db.session.commit()

    emit_state(["assignments"])
    return assignment_json(assignment)


@api("add_location")
@is_staff
def add_location(data):
    name = data["name"]
    if name == "Online":
        return
    location = Location(name=name, course=get_course(), link="", online=False)
    db.session.add(location)
    db.session.commit()

    emit_state(["locations"])
    db.session.refresh(location)
    return location_json(location)


@api("update_location")
@is_staff
def update_location(data):
    location = Location.query.filter_by(id=data["id"], course=get_course()).one()
    if "name" in data:
        location.name = data["name"]
    if "visible" in data:
        location.visible = data["visible"]
    if "link" in data:
        location.link = data["link"]
    if "online" in data:
        location.online = data["online"]
    if location.link:
        location.online = True
    location.link = location.link and urljoin("https://", location.link)
    if location.name == "Online":
        return
    db.session.commit()

    emit_state(["locations"])
    return location_json(location)


@api("update_config")
@is_staff
def update_config(data):
    config = {}
    if "keys" in data:
        config = {k: v for k, v in zip(data["keys"], data["values"]) if v is not None}
    elif "key" in data:
        config = {data["key"]: data["value"]}
    if "queue_magic_word_mode" in config:
        if config["queue_magic_word_mode"] == "timed_numeric":
            config["queue_magic_word_data"] = (
                format(random.randrange(2**64), "x") + ":60:0:9999"
            )
    for key, value in config.items():
        entry = ConfigEntry.query.filter_by(key=key, course=get_course()).one()
        entry.value = value
    db.session.commit()

    emit_state(["config", "locations"])

    return config_json()


@api("update_staff_online_setup")
@is_staff
def update_staff_online_setup(data):
    if "staff-call-link" in data:
        current_user.call_url = data["staff-call-link"] and urljoin(
            "https://", data["staff-call-link"]
        )
    if "staff-doc-link" in data:
        current_user.doc_url = data["staff-doc-link"] and urljoin(
            "https://", data["staff-doc-link"]
        )
    db.session.add(current_user)

    db.session.commit()

    emit_state(["current_user"])
    emit_state(["tickets"])


@api("send_chat_message")
@logged_in
def send_chat_message(data):
    mode = data.get("mode")
    if mode not in ("ticket", "group"):
        return socket_error("Messages can only be sent on a ticket or group")
    event_id = data["id"]

    message = ChatMessage(user=current_user, course=get_course(), body=data["content"])

    if mode == "ticket":
        ticket = Ticket.query.filter_by(course=get_course(), id=event_id).one()
        if not current_user.is_staff and ticket.user_id != current_user.id:
            return socket_unauthorized()
        message.ticket = ticket

    elif mode == "group":
        group = Group.query.filter_by(course=get_course(), id=event_id).one()
        if not current_user.is_staff and not is_member_of(group):
            return socket_unauthorized()
        message.group = group

    db.session.add(message)
    db.session.commit()

    if mode == "ticket":
        emit_event(message.ticket, TicketEventType.message_sent)
    elif mode == "group":
        emit_group_event(message.group, "message_sent")


@api("list_users")
@is_staff
def list_users():
    return [user_json(user) for user in User.query.filter_by(course=get_course()).all()]


@api("get_user")
@logged_in
def get_user(user_id):
    if user_id != current_user.id and not current_user.is_staff:
        return socket_unauthorized()
    user = User.query.filter_by(course=get_course(), id=user_id).one()
    tickets = (
        Ticket.query.filter(
            or_(Ticket.user_id == user.id, Ticket.helper_id == user.id),
            Ticket.course == get_course(),
        )
        .order_by(desc(Ticket.created))
        .options(joinedload(Ticket.user, innerjoin=True))
        .options(joinedload(Ticket.helper))
        .options(joinedload(Ticket.group))
        .all()
    )
    return {
        "user": user_json(user),
        "tickets": [ticket_json(ticket) for ticket in tickets],
    }


def leave_current_groups():
    prev_attendance = GroupAttendance.query.filter_by(
        user_id=current_user.id, group_attendance_status=GroupAttendanceStatus.present
    ).one_or_none()
    if prev_attendance:
        prev_attendance.group_attendance_status = GroupAttendanceStatus.gone
        db.session.commit()
        other_attendances = GroupAttendance.query.filter_by(
            group=prev_attendance.group,
            group_attendance_status=GroupAttendanceStatus.present,
        ).all()

        if prev_attendance.group.ticket and (
            not other_attendances
            or prev_attendance.group.ticket.user_id == current_user.id
        ):
            # delete the ticket if the group is closed or the ticket creator leaves
            prev_attendance.group.ticket.status = TicketStatus.deleted
            emit_event(prev_attendance.group.ticket, TicketEventType.delete)

        if not other_attendances:
            prev_attendance.group.group_status = GroupStatus.resolved
            db.session.commit()
            emit_group_event(prev_attendance.group, "group_closed")
        else:
            emit_group_event(prev_attendance.group, "group_left")


def process_call_link(link, location):
    if link:
        if location.link:
            if all(x.isdigit() for x in link):
                return "Breakout Room " + link
        else:
            return urljoin("https://", link)
    return link


@api("create_group")
@logged_in
def create_group(form):
    party_enabled = ConfigEntry.query.filter_by(
        course=get_course(), key="party_enabled"
    ).one()
    if party_enabled.value != "true":
        return socket_error("Party mode is not enabled.", category="warning")

    assignment_id = form.get("assignment_id")
    location_id = form.get("location_id")
    question = form.get("question")

    call_link = form.get("call-link", "")
    doc_link = form.get("doc-link", "")
    use_llm = parse_bool(form.get("use_llm")) if llm_tips_enabled() else False

    location = Location.query.filter_by(
        course=get_course(), id=location_id
    ).one_or_none()
    if not location:
        return socket_error(
            "Unknown location (id: {})".format(location_id), category="warning"
        )

    call_link = process_call_link(call_link, location)

    if doc_link:
        doc_link = urljoin("https://", doc_link)

    if assignment_id is None or location_id is None or not question:
        return socket_error("You must fill out all the fields", category="warning")

    assignment = Assignment.query.filter_by(
        course=get_course(), id=assignment_id
    ).one_or_none()
    if not assignment:
        return socket_error(
            "Unknown assignment (id: {})".format(assignment_id), category="warning"
        )

    if location.name == "Online" and not call_link:
        return socket_error("You must fill out all the fields", category="warning")

    leave_current_groups()

    group = Group(
        group_status=GroupStatus.active,
        assignment=assignment,
        location=location,
        description="Hi! Anyone else want to work on this problem with me?",
        question=question,
        course=get_course(),
        call_url=call_link,
        doc_url=doc_link,
        use_llm=use_llm,
    )

    db.session.add(group)

    group_attendance = GroupAttendance(
        group=group,
        user=current_user,
        group_attendance_status=GroupAttendanceStatus.present,
        course=get_course(),
    )

    db.session.add(group_attendance)

    db.session.commit()

    emit_group_event(group, "group_created")

    return socket_redirect(group_id=group.id)


@api("load_group")
@is_staff
def load_group(group_id):
    if not group_id:
        return socket_error("Invalid group ID")
    group = Group.query.filter_by(id=group_id, course=get_course()).one()
    if group:
        return group_json(group)


@api("join_group")
@logged_in
def join_group(group_id):
    group = Group.query.filter_by(
        id=group_id, course=get_course(), group_status=GroupStatus.active
    ).one()
    leave_current_groups()
    attendance = GroupAttendance(
        group=group,
        user=current_user,
        group_attendance_status=GroupAttendanceStatus.present,
        course=get_course(),
    )
    db.session.add(attendance)
    db.session.commit()

    emit_group_event(group, "group_joined")
    # The group's ticket, which the new member can now see in full.
    if group.ticket and group.ticket.status in active_statuses:
        add_response("event", {"type": "group_joined", "ticket": ticket_json(group.ticket)})

    return socket_redirect(group_id=group_id)


@api("leave_group")
@logged_in
def leave_group(group_id):
    leave_current_groups()
    return socket_redirect()


def apply_group_update(data, group=None):
    if not group:
        group_id = data["id"]
        group = Group.query.filter_by(id=group_id, course=get_course()).one()
    if "description" in data:
        group.description = data["description"]
    if "assignment_id" in data:
        group.assignment = Assignment.query.filter_by(
            course=get_course(), id=data["assignment_id"]
        ).one()
    if "question" in data:
        group.question = data["question"]
    if "location_id" in data:
        group.location = Location.query.filter_by(
            course=get_course(), id=data["location_id"]
        ).one()


@api("update_group")
@requires_group_access
def update_group(data, group):
    apply_group_update(data, group)
    db.session.commit()
    emit_group_event(group, "update_group")
    return group_json(group)


@api("update_groups")
@is_staff
def update_groups(arr):
    group_ids = [data["id"] for data in arr]
    groups = Group.query.filter(
        Group.id.in_(group_ids), Group.course == get_course()
    ).all()
    group_dict = {group.id: group for group in groups}
    for data in arr:
        apply_group_update(data, group_dict[data["id"]])
    db.session.commit()
    return emit_state(["groups"])


@api("create_group_ticket")
@requires_group_access
def create_group_ticket(data, group):
    is_queue_open = ConfigEntry.query.filter_by(
        course=get_course(), key="is_queue_open"
    ).one()
    if is_queue_open.value != "true":
        return socket_error("The queue is closed", category="warning")
    if (
        group.ticket
        and group.ticket.status not in [TicketStatus.resolved, TicketStatus.deleted]
        or Ticket.for_user(current_user)
    ):
        return socket_error("You are already on the queue", category="warning")

    ticket = Ticket(
        status=TicketStatus.pending,
        user=current_user,
        assignment=group.assignment,
        location=group.location,
        question=group.question,
        description="This ticket is associated with a group.",
        course=get_course(),
        call_url=group.call_url,
        doc_url=group.doc_url,
        use_llm=group.use_llm,
    )

    db.session.add(ticket)
    db.session.commit()

    group.ticket = ticket
    db.session.commit()

    emit_event(ticket, TicketEventType.create)
    request_llm_tips_if_enabled(ticket)
    emit_group_event(group, "group_ticket_created")


@api("delete_group")
@is_staff
def delete_group(group_id):
    group = Group.query.filter_by(id=group_id, course=get_course()).one()
    delete_group_worker(group, emit=True)
    db.session.commit()


def delete_group_worker(group, *, emit):
    group.group_status = GroupStatus.resolved
    for attendance in group.attendees:
        attendance.group_attendance_status = GroupAttendanceStatus.gone
    if emit:
        emit_group_event(group, "group_closed")
    if group.ticket:
        group.ticket.status = TicketStatus.deleted
        if emit:
            emit_event(group.ticket, TicketEventType.delete)


# After every route above is added to it.
app.register_blueprint(bp)
