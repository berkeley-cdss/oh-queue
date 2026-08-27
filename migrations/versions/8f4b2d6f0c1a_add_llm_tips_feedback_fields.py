"""Add LLM tips feedback fields to ticket

Revision ID: 8f4b2d6f0c1a
Revises: 4aa6d2a1a5ce
Create Date: 2026-02-12 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "8f4b2d6f0c1a"
down_revision = "4aa6d2a1a5ce"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("ticket", sa.Column("student_help_type", sa.String(64)))
    op.add_column("ticket", sa.Column("student_help_other", sa.Text()))
    op.add_column("ticket", sa.Column("staff_help_type", sa.String(64)))
    op.add_column("ticket", sa.Column("staff_help_other", sa.Text()))
    op.add_column("ticket", sa.Column("llm_tips_influence", sa.String(64)))


def downgrade():
    op.drop_column("ticket", "llm_tips_influence")
    op.drop_column("ticket", "staff_help_other")
    op.drop_column("ticket", "staff_help_type")
    op.drop_column("ticket", "student_help_other")
    op.drop_column("ticket", "student_help_type")
