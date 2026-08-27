#!/usr/bin/env python3

import os
from dotenv import load_dotenv

load_dotenv()

import datetime
import functools
import os
import random
import sys

import alembic
import alembic.command
import names

from alembic.config import Config
from flask import render_template
from flask_debugtoolbar import DebugToolbarExtension
from flask_migrate import Migrate


from common.course_config import get_course
from oh_queue import app
from oh_queue.models import (
    db,
    Assignment,
    Location,
    Ticket,
    TicketStatus,
    User,
    Appointment,
    AppointmentSignup,
    AppointmentStatus,
)

from werkzeug.serving import run_simple

os.environ["FLASK_APP"] = "manage.py"

migrate = Migrate(app, db)
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
    print("Seeding...")

    assignments = [
        Assignment(name=name, course=get_course(), visible=True)
        for name in ["Hog", "Maps", "Ants", "Scheme"]
    ]
    locations = [
        Location(name=name, course=get_course(), visible=True, online=False, link="")
        for name in ["109 Morgan", "241 Cory", "247 Cory"]
    ]
    questions = list(range(1, 16)) + ["Other", "EC", "Checkoff"]
    descriptions = ["", "I'm in the hallway", "SyntaxError on Line 5"]

    appointments = [
        Appointment(
            start_time=datetime.datetime.now()
            + datetime.timedelta(hours=random.randrange(-8, 50)),
            duration=datetime.timedelta(minutes=random.randrange(30, 120, 30)),
            location=random.choice(locations),
            capacity=5,
            status=AppointmentStatus.pending,
            course=get_course(),
        )
        for _ in range(70)
    ]

    for assignment in assignments:
        db.session.add(assignment)
    for location in locations:
        db.session.add(location)
    for appointment in appointments:
        db.session.add(appointment)

    db.session.commit()

    students = []

    for i in range(50):
        real_name = names.get_full_name()
        first_name, last_name = real_name.lower().split(" ")
        email = "{0}{1}@{2}".format(
            random.choice([first_name, first_name[0]]),
            random.choice([last_name, last_name[0]]),
            random.choice(["berkeley.edu", "gmail.com"]),
        )
        student = User.query.filter_by(email=email).one_or_none()
        if not student:
            student = User(name=real_name, email=email, course=get_course())
            students.append(student)
            db.session.add(student)
            db.session.commit()

        delta = datetime.timedelta(minutes=random.randrange(0, 30))
        ticket = Ticket(
            user=student,
            status=TicketStatus.pending,
            created=datetime.datetime.utcnow() - delta,
            assignment=random.choice(assignments),
            location=random.choice(locations),
            question=random.choice(questions),
            description=random.choice(descriptions),
            course=get_course(),
        )
        db.session.add(ticket)

    signups = [
        AppointmentSignup(
            appointment=random.choice(appointments),
            user=random.choice(students),
            assignment=random.choice(assignments),
            question=random.choice(questions),
            description=random.choice(descriptions),
            course=get_course(),
        )
        for _ in range(120)
    ]

    for signup in signups:
        db.session.add(signup)

    db.session.commit()


@app.cli.command("resetdb")
@not_in_production
def resetdb():
    print("Dropping tables...")
    db.drop_all(app=app)
    initdb()


@app.cli.command("initdb")
def initdb():
    print("Creating tables...")
    db.create_all(app=app)
    print("Stamping DB revision...")
    alembic.command.stamp(alembic_cfg, "head")

@app.cli.command("build")
@not_in_production
def build():
    with app.test_request_context():
        render_template("index.html", course_name="test")

@app.cli.command("run_server")
@not_in_production
def run_server(): 
    DebugToolbarExtension(app)
    
    host = app.config.get("HOST") or os.environ.get("HOST", "0.0.0.0")
    port = int(app.config.get("PORT") or os.environ.get("PORT", 3000))
    
    print(f"Starting development server on {host}:{port}...")
    run_simple(host, port, app, use_reloader=True, use_debugger=True)

if __name__ == "__main__":
    from flask.cli import main
    main()