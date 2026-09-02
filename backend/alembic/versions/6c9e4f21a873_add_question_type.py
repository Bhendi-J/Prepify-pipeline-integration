"""add question type

Revision ID: 6c9e4f21a873
Revises: 2d84f7c9b6e1
Create Date: 2026-09-02 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6c9e4f21a873"
down_revision: Union[str, Sequence[str], None] = "2d84f7c9b6e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "questions",
        sa.Column(
            "question_type",
            sa.String(length=50),
            server_default="short_answer",
            nullable=False,
        ),
    )
    op.alter_column("questions", "question_type", server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("questions", "question_type")
