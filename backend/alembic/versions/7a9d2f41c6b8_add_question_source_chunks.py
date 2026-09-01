"""add question source chunks

Revision ID: 7a9d2f41c6b8
Revises: f4a7d2c31a0e
Create Date: 2026-09-01 00:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a9d2f41c6b8"
down_revision: Union[str, Sequence[str], None] = "f4a7d2c31a0e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("questions_chunk_id_fkey", "questions", type_="foreignkey")
    op.alter_column("questions", "chunk_id", existing_type=sa.Integer(), nullable=True)
    op.create_foreign_key(
        "questions_chunk_id_fkey",
        "questions",
        "chunks",
        ["chunk_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "question_chunks",
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["chunk_id"], ["chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("question_id", "chunk_id"),
    )
    op.execute(
        """
        INSERT INTO question_chunks (question_id, chunk_id, position)
        SELECT id, chunk_id, 0
        FROM questions
        WHERE chunk_id IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("question_chunks")
    op.execute("DELETE FROM questions WHERE chunk_id IS NULL")
    op.drop_constraint("questions_chunk_id_fkey", "questions", type_="foreignkey")
    op.alter_column("questions", "chunk_id", existing_type=sa.Integer(), nullable=False)
    op.create_foreign_key(
        "questions_chunk_id_fkey",
        "questions",
        "chunks",
        ["chunk_id"],
        ["id"],
        ondelete="CASCADE",
    )
