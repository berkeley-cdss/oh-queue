import flask
from authlib.integrations.base_client import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import abort, current_app, redirect, render_template, request, session, url_for
from flask_login import LoginManager, login_user, logout_user
from markupsafe import escape

from oh_queue import canvas_service
from oh_queue.models import Account, ConfigEntry, Offering, User, db
from oh_queue.offering import current_offering, get_course, in_offering

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


def _after_login():
    return redirect(session.pop(AFTER_LOGIN_KEY, None) or url_for("offerings"))


def complete_login(token: dict):
    """Create or update the signed-in Account from a Canvas OAuth token response."""
    canvas_user_id = str(token["user"]["id"])
    access_token = token["access_token"]
    profile = canvas_service.get_profile(canvas_user_id, access_token)
    email = profile.get("primary_email") or profile.get("login_id")
    courses = canvas_service.get_user_courses(canvas_user_id, access_token)
    override_id = current_app.config.get("ADMIN_OVERRIDE_CANVAS_COURSE_ID")

    account = Account.query.filter_by(canvas_id=canvas_user_id).one_or_none()
    if account is None:
        account = Account(canvas_id=canvas_user_id)
        db.session.add(account)
    account.email = email
    account.name = profile.get("name") or email
    account.canvas_courses = courses
    account.is_global_admin = override_id is not None and str(override_id) in courses
    db.session.commit()
    login_user(account, remember=True)


def _only_registered_students() -> bool:
    entry = ConfigEntry.query.filter_by(key="only_registered_students", course=get_course()).one_or_none()
    return entry is not None and entry.value == "true"


def course_user(account: Account):
    """The account's User row in the current course, created on first visit.

    Staff status follows the account's Canvas roles from its last sign-in.
    Returns None if the course only lets in people on its roster and the
    account isn't on it.
    """
    canvas_id = current_offering().canvas_id
    is_staff = account.is_staff_in(canvas_id)
    if not is_staff and account.course_info(canvas_id) is None and _only_registered_students():
        return None
    course = get_course()
    user = User.query.filter_by(email=account.email, course=course).one_or_none()
    if user is None:
        user = User(email=account.email, name=account.name, is_staff=is_staff, course=course)
        db.session.add(user)
    elif (user.name, user.is_staff) == (account.name, is_staff):
        return user
    user.name = account.name
    user.is_staff = is_staff
    db.session.commit()
    return user


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
    def load_user(session_id):
        account_id = Account.parse_session_id(session_id)
        account = db.session.get(Account, account_id) if account_id else None
        if account is None or not in_offering():
            return account
        user = course_user(account)
        if user is None:
            abort(403, "This course's queue is only open to people on its bCourses roster. If you were "
                       "just added, accept the invitation in bCourses, then log out and sign in again.")
        return user

    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect(url_for("login", next=request.full_path.rstrip("?")))

    # Same routes as seating and sections.
    @app.route("/login/")
    def login():
        session[AFTER_LOGIN_KEY] = _safe_next(request.args.get("next"))
        if not app.config["CANVAS_CLIENT_ID"]:
            if app.config["ENV"] == "dev":
                return redirect(url_for("testing_login"))
            abort(503)
        return canvas.authorize_redirect(url_for("authorized", _external=True))

    @app.route("/authorized/")
    def authorized():
        try:
            token = canvas.authorize_access_token()
        except OAuthError as e:
            # The error comes from query parameters anyone can put in a link: escape it.
            return f"Access denied: {escape(e.description or e.error or 'unknown error')}", 403
        complete_login(token)
        return _after_login()

    # A POST, so a link or image on another site can't sign people out.
    @app.route("/logout/", methods=["POST"])
    def logout():
        logout_user()
        return redirect(url_for("index"))

    create_testing_login(app)


def create_testing_login(app: flask.Flask):
    """In development, a form for signing in as anyone, without Canvas."""

    @app.route("/testing-login/", strict_slashes=False)
    def testing_login():
        if app.config["ENV"] != "dev":
            abort(404)
        return render_template("login.html", title="Development Login", callback=url_for("testing_authorized"))

    @app.route("/testing-login/authorized", methods=["POST"], strict_slashes=False)
    def testing_authorized():
        """Sign in as anyone, as a TA or a student in every offering."""
        if app.config["ENV"] != "dev":
            abort(404)
        form = request.form
        is_staff = form.get("is_staff") == "on"
        email = form["email"]
        canvas_id = f"dev:{email}"
        account = Account.query.filter_by(canvas_id=canvas_id).one_or_none()
        if account is None:
            account = Account(canvas_id=canvas_id)
            db.session.add(account)
        account.email = email
        account.name = form["name"] or email
        account.is_global_admin = False
        account.canvas_courses = {
            str(o.canvas_id): {
                "name": o.name,
                "code": o.code,
                "start_at": o.start_at,
                "is_staff": is_staff,
                "is_admin": is_staff,
                "is_student": not is_staff,
            }
            for o in Offering.query.all()
        }
        db.session.commit()
        login_user(account, remember=True)
        return _after_login()
