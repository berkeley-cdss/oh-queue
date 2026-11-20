"""Remove appointments

Revision ID: 4370289bdaeb
Revises: b6e1c0d4a9f2
Create Date: 2026-11-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4370289bdaeb"
down_revision = "b6e1c0d4a9f2"
branch_labels = None
depends_on = None

# The appointment settings, with the values new courses started with.
REMOVED_CONFIG_ENTRIES = {
    "appointments_open": "false",
    "daily_appointment_limit": "2",
    "weekly_appointment_limit": "5",
    "simul_appointment_limit": "5",
    "auto_activate_appointments": "false",
    "auto_activate_appointments_frequency": "12",
    "auto_activate_appointments_range": "12",
    "always_show_appointment_join_call": "false",
    "recommend_appointments": "true",
    "appointment_mode_title": "Appointments",
    "appointment_prompt": "",
}

config_entries = sa.table(
    "config_entries",
    sa.column("key", sa.String),
    sa.column("value", sa.Text),
    sa.column("public", sa.Boolean),
    sa.column("course", sa.String),
)
chat_message = sa.table("chat_message", sa.column("appointment_id", sa.Integer))


def upgrade():
    # MySQL commits each schema change as it runs, so if one fails, the steps
    # before it stay done. The settings, which older code reads, go last.

    # The foreign key was created without a name, so look up the one the
    # database gave it. It goes before the index, which MySQL uses for it, and
    # before the column, which MySQL won't drop while the key exists. SQLite
    # doesn't name it, and batch mode drops it when it copies the table.
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("chat_message")
    with op.batch_alter_table("chat_message") as batch_op:
        for foreign_key in foreign_keys:
            if foreign_key["referred_table"] == "appointment" and foreign_key["name"]:
                batch_op.drop_constraint(foreign_key["name"], type_="foreignkey")
        batch_op.drop_index(op.f("ix_chat_message_appointment_id"))

    # Messages sent in appointments go with them.
    op.execute(chat_message.delete().where(chat_message.c.appointment_id.isnot(None)))
    with op.batch_alter_table("chat_message") as batch_op:
        batch_op.drop_column("appointment_id")

    op.drop_table("appointment_signup")
    op.drop_table("appointment")

    op.execute(
        config_entries.delete().where(config_entries.c.key.in_(REMOVED_CONFIG_ENTRIES))
    )


def downgrade():
    # The tables come back empty; the settings come back with their defaults.
    op.create_table(
        "appointment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("duration", sa.Interval(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("num_reminders_sent", sa.Integer(), nullable=False),
        sa.Column("private_pinged", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=False),
        sa.Column("helper_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=255), nullable=False),
        sa.Column("course", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["helper_id"], ["user.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["location.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["course", "helper_id", "location_id", "start_time", "status"]:
        op.create_index(op.f(f"ix_appointment_{column}"), "appointment", [column])

    op.create_table(
        "appointment_signup",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("appointment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("question", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("attendance_status", sa.String(length=255), nullable=False),
        sa.Column("course", sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(["appointment_id"], ["appointment.id"]),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignment.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["appointment_id", "assignment_id", "course", "user_id"]:
        op.create_index(
            op.f(f"ix_appointment_signup_{column}"), "appointment_signup", [column]
        )

    # The index goes first, so MySQL uses it for the foreign key, as in upgrade.
    with op.batch_alter_table("chat_message") as batch_op:
        batch_op.add_column(sa.Column("appointment_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            op.f("ix_chat_message_appointment_id"), ["appointment_id"]
        )
        batch_op.create_foreign_key(
            "fk_chat_message_appointment_id", "appointment", ["appointment_id"], ["id"]
        )

    courses = [
        course
        for (course,) in op.get_bind().execute(
            sa.select([config_entries.c.course]).distinct()
        )
    ]
    op.bulk_insert(
        config_entries,
        [
            {"key": key, "value": value, "public": True, "course": course}
            for course in courses
            for key, value in REMOVED_CONFIG_ENTRIES.items()
        ],
    )
