from os import getenv
import flask
from flask import abort, redirect, render_template, request, session
from flask_login import LoginManager, login_user, logout_user
import canvasapi

from common.course_config import get_course, get_bcourses_id
from common.oauth_client import create_oauth_client
from common.url_for import url_for
from oh_queue.models import User, db
import common.canvas_service as canvas_service

dev = getenv("ENV") != "prod"

def create_login_client(app: flask.Flask):
    login_manager = LoginManager()
    login_manager.init_app(app)

    def login(resp: dict):
        user_info = resp['user']
        user_id = user_info['id']
        user_email = canvas_service.get_email(user_id)
        user_name = canvas_service.get_name(user_id)
        user_courses = canvas_service.get_user_courses(user_id)
        app_course_id: int = get_bcourses_id()
        course = get_course()

        user = User.query.filter_by(
            email=user_email, course=course
        ).one_or_none()
        
        if user is None:
            user = User(
                email=user_email,
                name=user_name,
                is_staff=False,
                # is_admin=False,
                course=course
            )
            db.session.add(user)
        user.name = user_name or user_email

        try:
            app_course = canvas_service.get_course(app_course_id)
            user.is_staff = canvas_service.is_staff(app_course, user_id)
            user.is_admin = canvas_service.is_admin(app_course, user_id)
        except canvasapi.exceptions.Forbidden as e:
            # Bypass for high-level admins/instructors
            if 1549197 in [c.id for c in user_courses]: 
                user.is_staff = True
                user.is_admin = True
            else:
                raise e
        db.session.commit()
        login_user(user, remember=True)

    create_oauth_client(app, "oh", success_callback=login)

    @login_manager.user_loader
    def load_user(user_id):
        course = get_course()
        return User.query.filter_by(id=user_id, course=course).one_or_none()
    
    @app.route("/oauth/logout")
    def logout():
        logout_user()
        return redirect(url_for("index"))

    @app.route("/testing-login/", strict_slashes=False)
    def testing_login():
        if not dev:
            abort(404)
        return render_template("login.html", callback=url_for("testing_authorized"))

    @app.route("/testing-login/authorized", methods=["POST"], strict_slashes=False)
    def testing_authorized():
        if not dev:
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