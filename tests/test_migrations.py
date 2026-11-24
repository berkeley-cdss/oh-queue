"""The migrations that remove Slack notifications, okpy backup links, appointments
and LLM tips.

The migrations before them were written for MySQL and don't run on SQLite, so
the tests start from the current tables, as `manage.py initdb` makes them.
Indexes the migrations drop are renamed first, as copying the production
database from MySQL to Postgres renamed them (idx_<number>_<name>).
"""

import sqlalchemy as sa
from flask_migrate import downgrade, stamp, upgrade

from oh_queue.models import Account, Offering, db

BEFORE = "8f4b2d6f0c1a"
REMOVED_KEYS = [
    "show_okpy_backups",
    "slack_notif_long_queue",
    "slack_notif_appt_summary",
    "slack_notif_missed_appt",
    "slack_notif_missed_appt_private",
]


def sql(statement, **params):
    with db.engine.begin() as conn:
        result = conn.execute(sa.text(statement), params)
        return result.fetchall() if result.returns_rows else None


def tables():
    return set(sa.inspect(db.engine).get_table_names())


def test_removes_slack_and_okpy(app_context):
    try:
        check_upgrade_and_downgrade()
    finally:
        # Not one of the app's tables, so the app fixture doesn't drop them.
        sql("DROP TABLE IF EXISTS alembic_version")
        sql("DROP TABLE IF EXISTS notification_state")


def check_upgrade_and_downgrade():
    sql("""CREATE TABLE notification_state (id INTEGER PRIMARY KEY, last_queue_ping DATETIME NOT NULL,
           last_appointment_notif DATETIME NOT NULL, domain VARCHAR(255) NOT NULL, course VARCHAR(255) NOT NULL)""")
    sql("CREATE INDEX idx_18236_ix_notification_state_course ON notification_state (course)")
    sql("INSERT INTO notification_state VALUES (1, '2026-01-01', '2026-01-01', 'oh.example.edu', 'cs61a')")
    for course in ("cs61a", "data8"):
        for key in REMOVED_KEYS + ["is_queue_open"]:
            sql("INSERT INTO config_entries (key, value, public, course) VALUES (:key, 'true', 1, :course)",
                key=key, course=course)
    stamp(revision=BEFORE)

    upgrade(revision="b6e1c0d4a9f2")

    assert "notification_state" not in tables()
    # Every course's Slack and okpy settings go; other settings stay.
    assert sorted(sql("SELECT course, key FROM config_entries")) == [
        ("cs61a", "is_queue_open"), ("data8", "is_queue_open")]

    downgrade(revision=BEFORE)

    assert "notification_state" in tables()
    assert sql("SELECT * FROM notification_state") == []
    assert "ix_notification_state_course" in {i["name"] for i in sa.inspect(db.engine).get_indexes("notification_state")}

    upgrade(revision="b6e1c0d4a9f2")
    assert "notification_state" not in tables()


def test_adds_offerings_and_accounts(app_context):
    try:
        sql("INSERT INTO config_entries (key, value, public, course) VALUES ('is_queue_open', 'true', 1, 'cs61a')")
        stamp(revision="d3a7e5f1c0b2")
        downgrade(revision="4370289bdaeb")
        assert not {"offerings", "account"} & tables()
        assert sorted(sql("SELECT key, value FROM config_entries")) == [
            ("is_queue_open", "true"), ("only_registered_students", "false")]

        upgrade(revision="d3a7e5f1c0b2")
        assert {"offerings", "account"} <= tables()
        # Courses are only open to people enrolled in them, so the setting goes.
        assert sql("SELECT key FROM config_entries") == [("is_queue_open",)]
        indexes = {i["name"]: i["unique"] for t in ("offerings", "account")
                   for i in sa.inspect(db.engine).get_indexes(t)}
        assert indexes == {"ix_offerings_canvas_id": 1, "ix_account_canvas_id": 1, "ix_account_email": 0}
        # The models use the migrated tables.
        db.session.add(Offering(canvas_id=101, key="cs61a", name="CS 61A"))
        db.session.add(Account(canvas_id="42", email="a@example.edu", name="A", canvas_courses={"101": {}}))
        db.session.commit()
        assert Account.query.one().canvas_courses == {"101": {}}
    finally:
        db.session.rollback()
        sql("DROP TABLE IF EXISTS alembic_version")


def test_it_is_the_only_head(app_context):
    from alembic.script import ScriptDirectory

    config = app_context.extensions["migrate"].migrate.get_config()
    assert ScriptDirectory.from_config(config).get_heads() == ["42b35af5ed41"]


APPOINTMENT_KEYS = [
    "appointments_open",
    "daily_appointment_limit",
    "weekly_appointment_limit",
    "simul_appointment_limit",
    "auto_activate_appointments",
    "auto_activate_appointments_frequency",
    "auto_activate_appointments_range",
    "always_show_appointment_join_call",
    "recommend_appointments",
    "appointment_mode_title",
    "appointment_prompt",
]


def columns(table):
    return {c["name"] for c in sa.inspect(db.engine).get_columns(table)}


def test_removes_appointments(app_context):
    try:
        check_appointments_upgrade_and_downgrade()
    finally:
        sql("DROP TABLE IF EXISTS alembic_version")
        sql("DROP TABLE IF EXISTS appointment_signup")
        sql("DROP TABLE IF EXISTS appointment")


def check_appointments_upgrade_and_downgrade():
    # The app's tables are the ones after the migration; going down puts the
    # appointment tables and settings back.
    for course in ("cs61a", "data8"):
        sql("INSERT INTO config_entries (key, value, public, course) VALUES ('is_queue_open', 'true', 1, :course)",
            course=course)
    stamp(revision="4370289bdaeb")
    downgrade(revision="b6e1c0d4a9f2")

    assert {"appointment", "appointment_signup"} <= tables()
    assert "appointment_id" in columns("chat_message")
    sql("DROP INDEX ix_chat_message_appointment_id")
    sql("CREATE INDEX idx_18176_ix_chat_message_appointment_id ON chat_message (appointment_id)")
    assert sorted(sql("SELECT course, key, value FROM config_entries WHERE key = 'appointment_mode_title'")) == [
        ("cs61a", "appointment_mode_title", "Appointments"),
        ("data8", "appointment_mode_title", "Appointments")]

    sql("INSERT INTO user (id, email, name, course) VALUES (1, 'a@example.edu', 'A', 'cs61a')")
    sql("INSERT INTO location (id, name, online, link, course) VALUES (1, 'Cory', 0, '', 'cs61a')")
    sql("INSERT INTO assignment (id, name, course) VALUES (1, 'Hog', 'cs61a')")
    sql("""INSERT INTO ticket (id, status, user_id, assignment_id, location_id, question, course)
           VALUES (1, 'pending', 1, 1, 1, '1', 'cs61a')""")
    sql("""INSERT INTO appointment (id, start_time, duration, capacity, num_reminders_sent, private_pinged,
           description, location_id, status, course)
           VALUES (1, '2026-01-01', '1970-01-01 01:00:00', 5, 0, 0, '', 1, 'pending', 'cs61a')""")
    sql("""INSERT INTO appointment_signup (id, appointment_id, user_id, question, attendance_status, course)
           VALUES (1, 1, 1, '1', 'unknown', 'cs61a')""")
    sql("INSERT INTO chat_message (id, body, user_id, appointment_id, course) VALUES (1, 'appt', 1, 1, 'cs61a')")
    sql("INSERT INTO chat_message (id, body, user_id, ticket_id, course) VALUES (2, 'ticket', 1, 1, 'cs61a')")

    upgrade(revision="4370289bdaeb")

    assert not {"appointment", "appointment_signup"} & tables()
    assert "appointment_id" not in columns("chat_message")
    # Appointment messages go; ticket messages stay.
    assert sql("SELECT id, body, ticket_id FROM chat_message") == [(2, "ticket", 1)]
    assert "ix_chat_message_ticket_id" in {i["name"] for i in sa.inspect(db.engine).get_indexes("chat_message")}
    # Every course's appointment settings go; other settings stay.
    assert sorted(sql("SELECT course, key FROM config_entries")) == [
        ("cs61a", "is_queue_open"), ("data8", "is_queue_open")]

    downgrade(revision="b6e1c0d4a9f2")
    assert sql("SELECT * FROM appointment") == []
    assert sorted(sql("SELECT key FROM config_entries WHERE course = 'cs61a'")) == sorted(
        [(key,) for key in APPOINTMENT_KEYS + ["is_queue_open"]])
    upgrade(revision="4370289bdaeb")
    assert not {"appointment", "appointment_signup"} & tables()


LLM_TICKET_COLUMNS = {"llm_tips", "use_llm", "student_help_type", "student_help_other",
                      "staff_help_type", "staff_help_other", "llm_tips_influence"}


def test_removes_llm_tips(app_context):
    try:
        for course in ("cs61a", "data8"):
            sql("INSERT INTO config_entries (key, value, public, course) VALUES ('is_queue_open', 'true', 1, :course)",
                course=course)
        stamp(revision="42b35af5ed41")
        downgrade(revision="d3a7e5f1c0b2")
        assert LLM_TICKET_COLUMNS <= columns("ticket")
        assert "use_llm" in columns("group")
        # The setting comes back off, once per course.
        assert sorted(sql("SELECT course, key, value FROM config_entries WHERE key = 'enable_llm_features'")) == [
            ("cs61a", "enable_llm_features", "false"), ("data8", "enable_llm_features", "false")]
        sql("UPDATE config_entries SET value = 'true' WHERE key = 'enable_llm_features' AND course = 'cs61a'")

        sql("INSERT INTO user (id, email, name, course) VALUES (1, 'a@example.edu', 'A', 'cs61a')")
        sql("INSERT INTO location (id, name, online, link, course) VALUES (1, 'Cory', 0, '', 'cs61a')")
        sql("INSERT INTO assignment (id, name, course) VALUES (1, 'Hog', 'cs61a')")
        sql("""INSERT INTO ticket (id, status, user_id, assignment_id, location_id, question, course,
               llm_tips, use_llm, staff_help_type, llm_tips_influence)
               VALUES (1, 'pending', 1, 1, 1, '1', 'cs61a', 'Try this', 1, 'debugging', 'helpful')""")

        upgrade(revision="42b35af5ed41")

        assert not LLM_TICKET_COLUMNS & columns("ticket")
        assert "use_llm" not in columns("group")
        assert sql("SELECT id, question FROM ticket") == [(1, "1")]
        assert sorted(sql("SELECT course, key FROM config_entries")) == [
            ("cs61a", "is_queue_open"), ("data8", "is_queue_open")]
    finally:
        sql("DROP TABLE IF EXISTS alembic_version")
