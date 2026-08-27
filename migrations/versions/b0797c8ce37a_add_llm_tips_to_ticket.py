"""Add llm tips column to ticket

Revision ID: b0797c8ce37a
Revises: 3d327f052dac
Create Date: 2025-02-14 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b0797c8ce37a"
down_revision = "3d327f052dac"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ticket", sa.Column("llm_tips", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("ticket", "llm_tips")
