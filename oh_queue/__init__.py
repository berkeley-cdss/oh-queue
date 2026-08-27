import logging

from flask_session import Session
from datetime import timedelta
from oh_queue.login import create_login_client

# Flask-related stuff
from datetime import datetime, timedelta

from flask import Flask
from oh_queue.models import (
    Appointment,
    AppointmentStatus,
    ConfigEntry,
    get_current_time,
)
from flask_compress import Compress

from common.jobs import job
from common.course_config import get_course
from oh_queue import assets
from oh_queue.models import (
    Group,
    GroupAttendance,
    GroupAttendanceStatus,
    GroupStatus,
    db,
    TicketStatus,
)
from oh_queue.slack import worker

logging.basicConfig(level=logging.INFO)

# Initialize the application
app = Flask(__name__)
app.config.from_object("config")
app.url_map.strict_slashes = False

app.jinja_env.globals.update(
    {"TicketStatus": TicketStatus, "assets_env": assets.assets_env}
)

db.init_app(app)

# Initialize Canvas login
create_login_client(app)

# Configure server-side sessions (matching the sections app)
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY'] = db
app.config['SESSION_SQLALCHEMY_TABLE'] = 'flask_sessions'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
Session(app)

# Import views
import oh_queue.views


@job(app, "slack_notify")
def slack_poll():
    worker(app)


@job(app, "clear_inactive_groups")
def clear_inactive_groups():
    active_groups = Group.query.filter_by(group_status=GroupStatus.active).all()
    for group in active_groups:
        for attendance in group.attendees:
            if (
                attendance.group_attendance_status == GroupAttendanceStatus.present
                and attendance.user.heartbeat_time
                and attendance.user.heartbeat_time
                > datetime.utcnow() - timedelta(minutes=3)
            ):
                break
        else:
            oh_queue.views.delete_group_worker(group, emit=False)
    db.session.commit()


@job(app, "auto_activate_appointments")
def auto_activate_appointments():
    auto_activate = (
        ConfigEntry.query.filter_by(
            course=get_course(), key="auto_activate_appointments"
        )
        .one()
        .value
        == "true"
    )
    if not auto_activate:
        return
    load_frequency = int(
        ConfigEntry.query.filter_by(
            course=get_course(), key="auto_activate_appointments_frequency"
        )
        .one()
        .value
    )
    load_range = int(
        ConfigEntry.query.filter_by(
            course=get_course(), key="auto_activate_appointments_range"
        )
        .one()
        .value
    )
    current_time = round_hour(get_current_time())
    diff = current_time - datetime(2000, 1, 1)
    hours = diff.days * 24 + diff.seconds // 3600
    # check if right hour to activate appointments
    if hours % load_frequency != 0:
        return
    # load in the next set of appointments
    appointments = Appointment.query.filter(
        Appointment.course == get_course(),
        Appointment.helper_id != None,
        Appointment.status == AppointmentStatus.hidden,
        Appointment.start_time >= current_time,
        Appointment.start_time < current_time + timedelta(hours=load_range),
    )
    appointments.update(
        {Appointment.status: AppointmentStatus.pending}, synchronize_session=False
    )
    db.session.commit()


def round_hour(t):
    # Rounds to nearest hour by adding a timedelta hour if minute >= 30
    round_up = timedelta(hours=t.minute // 30)
    return t.replace(second=0, microsecond=0, minute=0, hour=t.hour) + round_up


# Caching
@app.after_request
def after_request(response):
    cache_control = "no-store"
    response.headers.add("Cache-Control", cache_control)
    return response


Compress(app)
