"""Add retry-safe practice submissions.

Revision ID: 8d92f0a63b17
Revises: 6c9e4f21a873
"""
from alembic import op
import sqlalchemy as sa

revision = "8d92f0a63b17"
down_revision = "6c9e4f21a873"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("attempts", sa.Column("submission_id", sa.Uuid(), nullable=True))
    op.create_unique_constraint(
        "uq_attempt_submission", "attempts", ["user_id", "question_id", "submission_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_attempt_submission", "attempts", type_="unique")
    op.drop_column("attempts", "submission_id")
