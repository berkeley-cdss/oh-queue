"""Landing page and course offering pages, with seating's and sections' routes and layout."""

import click
import flask
from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from oh_queue.models import Offering, can_be_offering, db


def _categorized_offerings(account):
    """Set-up offerings the account is staff in, a student in, or otherwise
    enrolled in, like seating's offerings page."""
    # Skip too-big IDs, which Postgres refuses to compare with the column.
    canvas_ids = [int(i) for i in account.canvas_courses if can_be_offering(i)]
    existing = Offering.query.filter(Offering.canvas_id.in_(canvas_ids)).all()
    staff, students, other = [], [], []
    for offering in existing:
        info = account.canvas_courses[str(offering.canvas_id)]
        # Offerings linked from the per-course sites start without Canvas details.
        if offering.code is None:
            offering.name, offering.code, offering.start_at = info["name"], info["code"], info["start_at"]
        if info["is_staff"] or account.is_global_admin:
            staff.append(offering)
        elif info["is_student"]:
            students.append(offering)
        else:
            other.append(offering)
    if account.is_global_admin:
        staff += Offering.query.filter(Offering.canvas_id.notin_(canvas_ids)).all()
    db.session.commit()

    def newest_first(offerings):
        return sorted(offerings, key=lambda o: (o.start_at or "", o.display_name), reverse=True)

    return newest_first(staff), newest_first(students), newest_first(other)


def create_offering_pages(app: flask.Flask):
    @app.route("/")
    def index():
        if current_user.is_authenticated:
            return redirect(url_for("offerings"))
        return render_template("pages/landing.html", title="Office Hours Queue")

    @app.route("/offerings")
    @login_required
    def offerings():
        staff, students, other = _categorized_offerings(current_user)
        return render_template(
            "pages/select_offering.html",
            title="Select a Course Offering",
            staff_offerings_existing=staff,
            student_offerings_existing=students,
            other_offerings_existing=other,
            removable_ids={o.canvas_id for o in staff if current_user.is_admin_in(o.canvas_id)},
        )

    @app.route("/offerings/new", methods=["GET", "POST"])
    @login_required
    def add_offerings():
        existing = {c.canvas_id for c in Offering.query.with_entities(Offering.canvas_id)}
        candidates = {
            int(canvas_id): info
            for canvas_id, info in current_user.canvas_courses.items()
            if info["is_staff"] and can_be_offering(canvas_id) and int(canvas_id) not in existing
        }
        if not candidates:
            flash("No more new courses to import.", "info")
            return redirect(url_for("offerings"))
        if request.method == "POST":
            chosen = [int(i) for i in request.form.getlist("offerings") if i.isdigit() and int(i) in candidates]
            if not chosen:
                flash("No course offering imported.", "info")
                return redirect(url_for("offerings"))
            db.session.add_all(
                Offering(canvas_id=i, key=str(i), name=candidates[i]["name"],
                         code=candidates[i]["code"], start_at=candidates[i]["start_at"])
                for i in chosen
            )
            try:
                db.session.commit()
            except IntegrityError:
                # Someone else imported one of them since the page loaded.
                db.session.rollback()
                flash("Someone else just imported one of those courses. Check the list, then try again.", "info")
                return redirect(url_for("offerings"))
            flash(f"Imported {len(chosen)} course offerings.", "success")
            return redirect(url_for("offerings"))
        rows = sorted(candidates.items(), key=lambda item: (item[1]["start_at"] or "", item[1]["name"]), reverse=True)
        return render_template("pages/new_offerings.html", title="Add New Course Offerings", candidates=rows)

    @app.route("/offerings/<int:canvas_id>/remove", methods=["POST"])
    @login_required
    def remove_offering(canvas_id):
        """Take an offering off the site, as in sections, but keep its tickets
        and settings: they're stored under its key, not linked to the Offering
        row, so importing the course again brings them back."""
        offering = Offering.for_canvas_id(canvas_id)
        if offering is None:
            abort(404)
        if not current_user.is_admin_in(canvas_id):
            abort(403, "Only course admins (instructors and Lead TAs) can remove an offering.")
        # Read before the delete expires them.
        key, name, display_name = offering.key, offering.name, offering.display_name
        db.session.delete(offering)
        db.session.commit()
        if key == str(canvas_id):
            flash(f"Hid {display_name}. Its tickets and settings are kept; "
                  "import it again to restore them.", "success")
        else:
            # Linked from a per-course site: importing would start over under a
            # new key, and linking it again is a command only a maintainer can
            # run, so the command goes in the log for them.
            flash(f"Hid {display_name}. Its tickets and settings are kept under "
                  f"'{key}'. Ask a maintainer to restore them.", "success")
            current_app.logger.info(
                "%s removed offering %s (key %s); to restore it, run: "
                "flask link-offering %s %s \"%s\"",
                current_user.email, canvas_id, key, canvas_id, key, name)
        return redirect(url_for("offerings"))

    create_link_offering_command(app)


def create_link_offering_command(app: flask.Flask):
    @app.cli.command("link-offering")
    @click.argument("canvas_id", type=int)
    @click.argument("key")
    @click.argument("name")
    def link_offering(canvas_id, key, name):
        """Set up CANVAS_ID using existing data stored under KEY (e.g. cs61a).

        NAME is shown until a course member signs in, which fills in the
        course's Canvas name, code and start date.
        """
        if not can_be_offering(canvas_id):
            raise click.ClickException(f"Canvas course {canvas_id}'s ID is too big.")
        if Offering.for_canvas_id(canvas_id) or Offering.query.filter_by(key=key).first():
            raise click.ClickException(f"Canvas course {canvas_id} or key '{key}' is already linked.")
        db.session.add(Offering(canvas_id=canvas_id, key=key, name=name))
        db.session.commit()
        click.echo(f"Linked Canvas course {canvas_id} to '{key}' as {name}.")
