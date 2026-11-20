"""The migration that removes Slack notifications and okpy backup links.

The migrations before it were written for MySQL and don't run on SQLite, so
the test starts from the current tables, as `manage.py initdb` makes them,
plus the table the migration drops.
"""

import sqlalchemy as sa
from flask_migrate import downgrade, stamp, upgrade

from oh_queue.models import db

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


def test_removes_slack_and_okpy(app):
    try:
        check_upgrade_and_downgrade()
    finally:
        # Not one of the app's tables, so the app fixture doesn't drop them.
        sql("DROP TABLE IF EXISTS alembic_version")
        sql("DROP TABLE IF EXISTS notification_state")


def check_upgrade_and_downgrade():
    sql("""CREATE TABLE notification_state (id INTEGER PRIMARY KEY, last_queue_ping DATETIME NOT NULL,
           last_appointment_notif DATETIME NOT NULL, domain VARCHAR(255) NOT NULL, course VARCHAR(255) NOT NULL)""")
    sql("CREATE INDEX ix_notification_state_course ON notification_state (course)")
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


def test_it_is_the_only_head(app):
    from alembic.script import ScriptDirectory

    config = app.extensions["migrate"].migrate.get_config()
    assert ScriptDirectory.from_config(config).get_heads() == ["b6e1c0d4a9f2"]
