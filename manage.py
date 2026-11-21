#!/usr/bin/env python3

import datetime
import functools
import os
import random
import sys

import alembic
import alembic.command
from alembic.config import Config
from dotenv import load_dotenv
from flask import render_template, url_for
from flask_migrate import Migrate
from werkzeug.serving import run_simple

# Before importing the app: config.py reads the environment when it's imported.
load_dotenv()

from oh_queue import app  # noqa: E402
from oh_queue.models import (  # noqa: E402
    Assignment,
    Location,
    Offering,
    Ticket,
    TicketStatus,
    User,
    db,
    utcnow,
)

os.environ["FLASK_APP"] = "manage.py"

migrate = Migrate(app, db)
# The UC Berkeley sandbox's test course, which seed_data sets up.
DEV_CANVAS_COURSE_ID = 157
alembic_cfg = Config("migrations/alembic.ini")


def not_in_production(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if app.config.get("ENV") == "prod":
            print("this command should not be run in production. Aborting")
            sys.exit(1)
        return f(*args, **kwargs)

    return wrapper


@app.cli.command("seed_data")
@not_in_production
def seed_data():
    import names  # from requirements-dev.txt

    print("Seeding...")

    # The UC Berkeley sandbox's test course, under the key the per-course sites used.
    offering = Offering.query.filter_by(canvas_id=DEV_CANVAS_COURSE_ID).one_or_none()
    if offering is None:
        offering = Offering(canvas_id=DEV_CANVAS_COURSE_ID, key="cs61a", name="CS 61A (sandbox)", code="CS 61A")
        db.session.add(offering)
    course = offering.key

    assignments = [
        Assignment(name=name, course=course, visible=True)
        for name in ["Hog", "Maps", "Ants", "Scheme"]
    ]
    locations = [
        Location(name=name, course=course, visible=True, online=False, link="")
        for name in ["109 Morgan", "241 Cory", "247 Cory"]
    ]
    questions = list(range(1, 16)) + ["Other", "EC", "Checkoff"]
    descriptions = ["", "I'm in the hallway", "SyntaxError on Line 5"]

    for assignment in assignments:
        db.session.add(assignment)
    for location in locations:
        db.session.add(location)

    db.session.commit()

    for i in range(50):
        real_name = names.get_full_name()
        first_name, last_name = real_name.lower().split(" ")
        email = "{0}{1}@{2}".format(
            random.choice([first_name, first_name[0]]),
            random.choice([last_name, last_name[0]]),
            random.choice(["berkeley.edu", "gmail.com"]),
        )
        student = User.query.filter_by(email=email, course=course).one_or_none()
        if not student:
            student = User(name=real_name, email=email, course=course)
            db.session.add(student)
            db.session.commit()

        delta = datetime.timedelta(minutes=random.randrange(0, 30))
        ticket = Ticket(
            user=student,
            status=TicketStatus.pending,
            created=utcnow() - delta,
            assignment=random.choice(assignments),
            location=random.choice(locations),
            question=random.choice(questions),
            description=random.choice(descriptions),
            course=course,
        )
        db.session.add(ticket)

    db.session.commit()
    with app.test_request_context():
        print(f"Seeded {offering.display_name}: open {url_for('offering.index', canvas_course_id=offering.canvas_id)}")


@app.cli.command("resetdb")
@not_in_production
def resetdb():
    print("Dropping tables...")
    db.drop_all()
    create_tables()


@app.cli.command("initdb")
def initdb():
    create_tables()


def create_tables():
    print("Creating tables...")
    db.create_all()
    print("Stamping DB revision...")
    alembic.command.stamp(alembic_cfg, "head")


@app.cli.command("build")
@not_in_production
def build():
    with app.test_request_context():
        render_template("index.html", course_name="test", base_path="/offerings/0")


@app.cli.command("run_server")
@not_in_production
def run_server():
    from flask_debugtoolbar import DebugToolbarExtension  # from requirements-dev.txt

    DebugToolbarExtension(app)

    host = app.config.get("HOST") or os.environ.get("HOST", "0.0.0.0")
    port = int(app.config.get("PORT") or os.environ.get("PORT", 3000))

    print(f"Starting development server on {host}:{port}...")
    run_simple(host, port, app, use_reloader=True, use_debugger=True)


if __name__ == "__main__":
    from flask.cli import main
    main()
