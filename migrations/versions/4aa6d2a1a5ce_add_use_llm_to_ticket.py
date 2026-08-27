"""Add use_llm column to ticket

Revision ID: 4aa6d2a1a5ce
Revises: b0797c8ce37a
Create Date: 2025-02-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "4aa6d2a1a5ce"
down_revision = "b0797c8ce37a"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "ticket",
        sa.Column("use_llm", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    with op.batch_alter_table("ticket") as batch_op:
        batch_op.alter_column("use_llm", server_default=None)
    op.add_column(
        "group",
        sa.Column("use_llm", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("group", "use_llm", server_default=None)


def downgrade():
    op.drop_column("group", "use_llm")
    op.drop_column("ticket", "use_llm")
