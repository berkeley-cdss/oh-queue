import logging
import os

from flask_session import Session
from datetime import timedelta
from oh_queue.errors import register_error_handlers
from oh_queue.login import create_login_client
from oh_queue.offerings import create_offering_pages
from oh_queue.schema_check import check_schema_before_requests

# Flask-related stuff

from flask import Flask
from flask_compress import Compress
from werkzeug.middleware.proxy_fix import ProxyFix

from oh_queue import assets
from oh_queue.jobs import job
from oh_queue.models import (
    Group,
    GroupAttendance,
    GroupAttendanceStatus,
    GroupStatus,
    db,
    TicketStatus,
    utcnow,
)

logging.basicConfig(level=logging.INFO)

MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations")

# Initialize the application
app = Flask(__name__)
app.config.from_object("config")
app.url_map.strict_slashes = False
# Behind Cloud Run's proxy, so external URLs (like the Canvas login callback) are https.
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1)

app.jinja_env.globals.update(
    {"TicketStatus": TicketStatus, "assets_env": assets.assets_env}
)

db.init_app(app)

# Initialize Canvas login and the pages for choosing a course
create_login_client(app)
create_offering_pages(app)
register_error_handlers(app)

# Configure server-side sessions
app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SESSION_SQLALCHEMY'] = db
app.config['SESSION_SQLALCHEMY_TABLE'] = 'flask_sessions'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = not app.debug
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
Session(app)

# Before the views' hooks, so a database that doesn't match the migrations
# gets an explanation rather than errors from its first query.
check_schema_before_requests(app, MIGRATIONS_DIR)


# For Cloud Run and the Dockerfile's health check.
@app.route("/health")
def health():
    return "ok"


# Import views, which need the app set up first
import oh_queue.views  # noqa: E402


@job(app, "clear_inactive_groups")
def clear_inactive_groups():
    active_groups = Group.query.filter_by(group_status=GroupStatus.active).all()
    for group in active_groups:
        for attendance in group.attendees:
            if (
                attendance.group_attendance_status == GroupAttendanceStatus.present
                and attendance.user.heartbeat_time
                and attendance.user.heartbeat_time
                > utcnow() - timedelta(minutes=3)
            ):
                break
        else:
            oh_queue.views.delete_group_worker(group, emit=False)
    db.session.commit()


# Caching
@app.after_request
def after_request(response):
    cache_control = "no-store"
    response.headers.add("Cache-Control", cache_control)
    return response


Compress(app)
