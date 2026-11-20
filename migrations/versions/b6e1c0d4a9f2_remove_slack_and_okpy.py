"""Remove Slack notifications and okpy backup links

Revision ID: b6e1c0d4a9f2
Revises: 8f4b2d6f0c1a
Create Date: 2026-11-19 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b6e1c0d4a9f2"
down_revision = "8f4b2d6f0c1a"
branch_labels = None
depends_on = None

REMOVED_CONFIG_KEYS = [
    "show_okpy_backups",
    "slack_notif_long_queue",
    "slack_notif_appt_summary",
    "slack_notif_missed_appt",
    "slack_notif_missed_appt_private",
]


def upgrade():
    config_entry = sa.table("config_entries", sa.column("key", sa.String))
    op.execute(config_entry.delete().where(config_entry.c.key.in_(REMOVED_CONFIG_KEYS)))
    # Dropping the table drops its index, whatever the database copy named it.
    op.drop_table("notification_state")


def downgrade():
    # The table comes back empty, and the config entries aren't restored.
    op.create_table(
        "notification_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("last_queue_ping", sa.DateTime(), nullable=False),
        sa.Column("last_appointment_notif", sa.DateTime(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("course", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_state_course"),
        "notification_state",
        ["course"],
        unique=False,
    )
