import flask
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import abort, redirect, render_template, request, session, url_for
from flask_login import LoginManager, login_user, logout_user
from markupsafe import escape

from oh_queue import canvas_service
from oh_queue.course import get_canvas_course_id, get_course
from oh_queue.models import User, db

AFTER_LOGIN_KEY = "after_login"


def _safe_next(target):
    # Only redirect back to paths on this site. Browsers read a backslash as a slash and drop tabs
    # and newlines, so /\evil.com and /<tab>/evil.com both go to //evil.com: refuse those too.
    if (
        target
        and target.startswith("/")
        and not target.startswith("//")
        and "\\" not in target
        and not any(ord(c) < 32 or ord(c) == 127 for c in target)
    ):
        return target
    return None


def complete_login(token: dict):
    """Create or update the signed-in User from a Canvas OAuth token response."""
    user_id = token["user"]["id"]
    access_token = token["access_token"]
    profile = canvas_service.get_profile(user_id, access_token)
    user_email = profile.get("primary_email")
    user_name = profile.get("name")
    course = get_course()

    user = User.query.filter_by(email=user_email, course=course).one_or_none()
    if user is None:
        user = User(email=user_email, name=user_name, is_staff=False, course=course)
        db.session.add(user)
    user.name = user_name or user_email

    # Members of the admin override course are staff even in a course they
    # aren't enrolled in.
    if canvas_service.in_admin_override_course(user_id, access_token):
        user.is_staff = True
    else:
        canvas_course = canvas_service.get_course(get_canvas_course_id(), access_token)
        user.is_staff = canvas_service.is_staff(canvas_course, user_id)
    db.session.commit()
    login_user(user, remember=True)


def create_login_client(app: flask.Flask):
    login_manager = LoginManager()
    login_manager.init_app(app)

    oauth = OAuth(app)
    canvas_server_url = app.config["CANVAS_SERVER_URL"]
    canvas = oauth.register(
        "canvas",
        client_id=app.config["CANVAS_CLIENT_ID"],
        client_secret=app.config["CANVAS_CLIENT_SECRET"],
        access_token_url=canvas_server_url + "login/oauth2/token",
        authorize_url=canvas_server_url + "login/oauth2/auth",
        client_kwargs={
            "scope": " ".join(canvas_service.SCOPES),
            # Canvas expects the client credentials in the POST body.
            "token_endpoint_auth_method": "client_secret_post",
        },
    )

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.filter_by(id=user_id, course=get_course()).one_or_none()

    @app.route("/oauth/canvas_login")
    def canvas_login():
        if not app.config["CANVAS_CLIENT_ID"]:
            abort(503)
        session[AFTER_LOGIN_KEY] = _safe_next(request.args.get("next"))
        return canvas.authorize_redirect(url_for("canvas_authorized", _external=True))

    @app.route("/oauth/canvas_authorized")
    def canvas_authorized():
        try:
            token = canvas.authorize_access_token()
        except OAuthError as e:
            # The error comes from query parameters anyone can put in a link: escape it.
            return f"Access denied: {escape(e.description or e.error or 'unknown error')}", 403
        complete_login(token)
        return redirect(session.pop(AFTER_LOGIN_KEY, None) or url_for("index"))

    @app.route("/oauth/logout")
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/testing-login/", strict_slashes=False)
    def testing_login():
        if app.config["ENV"] != "dev":
            abort(404)
        return render_template("login.html", callback=url_for("testing_authorized"))

    @app.route("/testing-login/authorized", methods=["POST"], strict_slashes=False)
    def testing_authorized():
        if app.config["ENV"] != "dev":
            abort(404)
        form = request.form
        is_staff = form.get("is_staff") == "on"
        course = get_course()
        user = User.query.filter_by(email=form["email"], course=course).one_or_none()
        if user is None:
            user = User(email=form["email"], name=form["name"], is_staff=is_staff, course=course)
            db.session.add(user)
        else:
            user.is_staff = is_staff
        db.session.commit()
        login_user(user, remember=True)
        return redirect(url_for("index"))
