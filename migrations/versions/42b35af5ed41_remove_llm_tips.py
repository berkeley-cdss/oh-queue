"""Remove LLM tips

Drops the tips, the opt-in, and the feedback asked for when resolving a
ticket that had tips, and the enable_llm_features setting.

Revision ID: 42b35af5ed41
Revises: d3a7e5f1c0b2
Create Date: 2026-11-23 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "42b35af5ed41"
down_revision = "d3a7e5f1c0b2"
branch_labels = None
depends_on = None

# The ticket's other LLM columns, all nullable.
TICKET_COLUMNS = {
    "llm_tips": sa.Text,
    "student_help_type": lambda: sa.String(64),
    "student_help_other": sa.Text,
    "staff_help_type": lambda: sa.String(64),
    "staff_help_other": sa.Text,
    "llm_tips_influence": lambda: sa.String(64),
}

config_entries = sa.table(
    "config_entries",
    sa.column("key", sa.String),
    sa.column("value", sa.Text),
    sa.column("public", sa.Boolean),
    sa.column("course", sa.String),
)


def upgrade():
    op.execute(config_entries.delete().where(config_entries.c.key == "enable_llm_features"))
    with op.batch_alter_table("ticket") as batch_op:
        for name in TICKET_COLUMNS:
            batch_op.drop_column(name)
        batch_op.drop_column("use_llm")
    with op.batch_alter_table("group") as batch_op:
        batch_op.drop_column("use_llm")


def downgrade():
    # The columns come back empty, and the setting comes back off.
    for table in ("ticket", "group"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("use_llm", sa.Boolean(), nullable=False, server_default=sa.false())
            )
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column("use_llm", server_default=None)
    with op.batch_alter_table("ticket") as batch_op:
        for name, type_ in TICKET_COLUMNS.items():
            batch_op.add_column(sa.Column(name, type_(), nullable=True))

    courses = [
        course
        for (course,) in op.get_bind().execute(
            sa.select(config_entries.c.course).distinct()
        )
    ]
    op.bulk_insert(
        config_entries,
        [
            {"key": "enable_llm_features", "value": "false", "public": True, "course": course}
            for course in courses
        ],
    )
