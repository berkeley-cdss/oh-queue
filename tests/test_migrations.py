"""The migrations that remove Slack notifications, okpy backup links, appointments
and LLM tips, add offerings, and merge users into one row per person.

The migrations before them were written for MySQL and don't run on SQLite, so
the tests start from the current tables, as `manage.py initdb` makes them.
Indexes the migrations drop are renamed first, as copying the production
database from MySQL to Postgres renamed them (idx_<number>_<name>).
"""

import pytest
import sqlalchemy as sa
from flask_migrate import downgrade, stamp, upgrade

from oh_queue.models import Heartbeat, Offering, User, db, utcnow

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


def before_one_user():
    """The user tables as they were before 5b9e2c7d1f30: a row per person per
    course, and an account per person who had signed in. The current tables
    stay, for the other tables' foreign keys; test_merges_users_into_one_per_person
    replaces them."""
    sql("""CREATE TABLE user (id INTEGER PRIMARY KEY, created DATETIME, email VARCHAR(255) NOT NULL,
           name VARCHAR(255) NOT NULL, is_staff BOOLEAN, course VARCHAR(255) NOT NULL, call_url VARCHAR(255),
           doc_url VARCHAR(255), heartbeat_time DATETIME)""")
    sql("""CREATE TABLE account (id INTEGER PRIMARY KEY, canvas_id VARCHAR(255) NOT NULL,
           email VARCHAR(255) NOT NULL, name VARCHAR(255) NOT NULL, is_global_admin BOOLEAN NOT NULL,
           canvas_courses JSON NOT NULL)""")
    sql("CREATE UNIQUE INDEX ix_account_canvas_id ON account (canvas_id)")
    sql("CREATE INDEX ix_account_email ON account (email)")


def drop_old_user_tables():
    # Not the app's tables, so the app fixture doesn't drop them.
    sql("DROP TABLE IF EXISTS user")
    sql("DROP TABLE IF EXISTS account")


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
        before_one_user()
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
        # The model uses the migrated table.
        db.session.add(Offering(canvas_id=101, key="cs61a", name="CS 61A"))
        db.session.commit()
        assert Offering.query.one().key == "cs61a"
    finally:
        db.session.rollback()
        sql("DROP TABLE IF EXISTS alembic_version")
        drop_old_user_tables()


def test_it_is_the_only_head(app_context):
    from alembic.script import ScriptDirectory

    config = app_context.extensions["migrate"].migrate.get_config()
    assert ScriptDirectory.from_config(config).get_heads() == ["5b9e2c7d1f30"]


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
        before_one_user()
        check_appointments_upgrade_and_downgrade()
    finally:
        drop_old_user_tables()
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
        before_one_user()
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
        drop_old_user_tables()
        sql("DROP TABLE IF EXISTS alembic_version")


def before_one_user_with_references():
    """before_one_user, with the tables referencing users pointing at the old table."""
    before_one_user()
    for table in ("heartbeat", "ticket_event", "group_attendance", "chat_message", "ticket", "users"):
        sql(f"DROP TABLE {table}")
    sql("""CREATE TABLE ticket (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES user (id),
           helper_id INTEGER REFERENCES user (id), course VARCHAR(255) NOT NULL)""")
    sql("CREATE INDEX ix_ticket_user_id ON ticket (user_id)")
    for table in ("ticket_event", "group_attendance", "chat_message"):
        sql(f"""CREATE TABLE {table} (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES user (id),
                course VARCHAR(255) NOT NULL)""")


def test_merges_users_into_one_per_person(app_context):
    try:
        before_one_user_with_references()
        sql("""INSERT INTO user (id, email, name, is_staff, course, call_url, doc_url) VALUES
               (10, 'ada@example.edu', 'Ada', 0, 'cs61a', 'meet.google.com/old', NULL),
               (11, 'ADA@example.edu', 'Ada L.', 1, 'data8', 'meet.google.com/new', NULL),
               (12, 'ada@example.edu', 'Ada L.', 0, 'data8', NULL, 'docs.google.com/ada'),
               (13, 'tutor@example.edu', 'Tutor', 1, 'cs61a', NULL, NULL),
               (14, 'bob@example.edu', 'Bob', NULL, 'cs61a', NULL, NULL)""")
        sql("""INSERT INTO account (id, canvas_id, email, name, is_global_admin, canvas_courses) VALUES
               (1, '555', 'ada@example.edu', 'Ada Lovelace', 0, '{"101": {"is_staff": false}}'),
               (2, '556', 'new@example.edu', 'Only Signed In', 1, '{}')""")
        sql("INSERT INTO ticket (id, user_id, helper_id, course) VALUES (1, 10, 13, 'cs61a'), (2, 14, 11, 'data8')")
        sql("INSERT INTO ticket_event (id, user_id, course) VALUES (1, 11, 'data8')")
        sql("INSERT INTO group_attendance (id, user_id, course) VALUES (1, 14, 'cs61a')")
        sql("INSERT INTO chat_message (id, user_id, course) VALUES (1, 12, 'data8')")
        stamp(revision="42b35af5ed41")

        upgrade(revision="5b9e2c7d1f30")

        assert not {"user", "account", "user_id_map"} & tables()
        people = {row.email: row for row in sql("SELECT * FROM users")}
        assert set(people) == {"ada@example.edu", "tutor@example.edu", "bob@example.edu", "new@example.edu"}
        ada = people["ada@example.edu"]
        # Signed-in people keep their Canvas name and details; the newest links win.
        assert (ada.name, ada.canvas_id, ada.canvas_courses) == ("Ada Lovelace", "555", '{"101": {"is_staff": false}}')
        assert (ada.call_url, ada.doc_url) == ("meet.google.com/new", "docs.google.com/ada")
        # Staff in data8, though an older row had her as a student there.
        assert (ada.staff_offerings, ada.student_offerings, ada.admin_offerings) == ("data8", "cs61a", "")
        assert people["tutor@example.edu"].staff_offerings == "cs61a"
        assert people["bob@example.edu"].student_offerings == "cs61a"  # an unknown role counts as student
        assert people["new@example.edu"].is_global_admin

        # Every reference now points at the merged person.
        ids = {email: row.id for email, row in people.items()}
        ada, tutor, bob = ids["ada@example.edu"], ids["tutor@example.edu"], ids["bob@example.edu"]
        assert sql("SELECT user_id, helper_id FROM ticket ORDER BY id") == [(ada, tutor), (bob, ada)]
        assert sql("SELECT user_id FROM ticket_event") == [(ada,)]
        assert sql("SELECT user_id FROM group_attendance") == [(bob,)]
        assert sql("SELECT user_id FROM chat_message") == [(ada,)]
        inspector = sa.inspect(db.engine)
        foreign_keys = {
            (table, tuple(fk["constrained_columns"]), fk["referred_table"])
            for table in ("ticket", "ticket_event", "group_attendance", "chat_message")
            for fk in inspector.get_foreign_keys(table)
        }
        assert foreign_keys == {
            ("ticket", ("user_id",), "users"), ("ticket", ("helper_id",), "users"),
            ("ticket_event", ("user_id",), "users"), ("group_attendance", ("user_id",), "users"),
            ("chat_message", ("user_id",), "users")}
        assert "ix_ticket_user_id" in {i["name"] for i in inspector.get_indexes("ticket")}

        # The models use the migrated tables.
        assert db.session.get(User, ada).staff_offerings == {"data8"}
        db.session.add(Heartbeat(user_id=ada, course="cs61a", time=utcnow()))
        db.session.commit()
        assert Heartbeat.query.one().user.email == "ada@example.edu"
    finally:
        db.session.rollback()
        drop_old_user_tables()
        sql("DROP TABLE IF EXISTS alembic_version")


def upgrade_raising(app):
    """Upgrade to 5b9e2c7d1f30 through Alembic, which raises the migration's own
    error, where Flask-Migrate's upgrade logs it and exits."""
    from alembic import command

    command.upgrade(app.extensions["migrate"].migrate.get_config(), "5b9e2c7d1f30")


def test_refuses_references_to_missing_users(app_context):
    try:
        before_one_user_with_references()
        sql("INSERT INTO user (id, email, name, is_staff, course) VALUES (1, 'a@example.edu', 'A', 0, 'cs61a')")
        sql("INSERT INTO ticket (id, user_id, helper_id, course) VALUES (1, 1, 7, 'cs61a'), (2, 1, 8, 'cs61a')")
        sql("INSERT INTO chat_message (id, user_id, course) VALUES (1, 9, 'cs61a')")
        stamp(revision="42b35af5ed41")
        with pytest.raises(RuntimeError, match=r"ticket.helper_id \(user ids 7, 8\); chat_message.user_id \(user ids 9\)"):
            upgrade_raising(app_context)
        # Nothing changed.
        assert {"user", "account"} <= tables() and "users" not in tables()
        assert sql("SELECT helper_id FROM ticket ORDER BY id") == [(7,), (8,)]
    finally:
        drop_old_user_tables()
        sql("DROP TABLE IF EXISTS alembic_version")


def test_refuses_two_bcourses_accounts_with_one_email(app_context):
    try:
        before_one_user_with_references()
        sql("""INSERT INTO account (id, canvas_id, email, name, is_global_admin, canvas_courses) VALUES
               (1, '555', 'ada@example.edu', 'Ada', 0, '{}'), (2, '777', 'ADA@example.edu', 'Ada', 0, '{}')""")
        stamp(revision="42b35af5ed41")
        with pytest.raises(RuntimeError, match=r"ADA@example.edu \(Canvas users 555 and 777\)"):
            upgrade_raising(app_context)
        assert {"user", "account"} <= tables() and "users" not in tables()
    finally:
        drop_old_user_tables()
        sql("DROP TABLE IF EXISTS alembic_version")
