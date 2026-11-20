"""Add offerings and accounts, so one site serves every course

Also removes the only_registered_students setting: a course's queue is now
only open to people enrolled in it on bCourses.

Revision ID: d3a7e5f1c0b2
Revises: 4370289bdaeb
Create Date: 2026-11-20 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "d3a7e5f1c0b2"
down_revision = "4370289bdaeb"
branch_labels = None
depends_on = None

config_entries = sa.table(
    "config_entries",
    sa.column("key", sa.String),
    sa.column("value", sa.Text),
    sa.column("public", sa.Boolean),
    sa.column("course", sa.String),
)


def upgrade():
    # New tables: existing rows keep their course keys, and an offering
    # moved from a per-course site is linked to its key with `flask link-offering`.
    op.create_table(
        "offerings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canvas_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=True),
        sa.Column("start_at", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key"),
    )
    op.create_index("ix_offerings_canvas_id", "offerings", ["canvas_id"], unique=True)

    op.create_table(
        "account",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("canvas_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_global_admin", sa.Boolean(), nullable=False),
        sa.Column("canvas_courses", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_canvas_id", "account", ["canvas_id"], unique=True)
    op.create_index("ix_account_email", "account", ["email"], unique=False)

    op.execute(config_entries.delete().where(config_entries.c.key == "only_registered_students"))


def downgrade():
    # Back with its default, off, in every course.
    courses = [
        course
        for (course,) in op.get_bind().execute(sa.select(config_entries.c.course).distinct())
    ]
    op.bulk_insert(
        config_entries,
        [{"key": "only_registered_students", "value": "false", "public": True, "course": course}
         for course in courses],
    )
    op.drop_index("ix_account_email", table_name="account")
    op.drop_index("ix_account_canvas_id", table_name="account")
    op.drop_table("account")
    op.drop_index("ix_offerings_canvas_id", table_name="offerings")
    op.drop_table("offerings")
