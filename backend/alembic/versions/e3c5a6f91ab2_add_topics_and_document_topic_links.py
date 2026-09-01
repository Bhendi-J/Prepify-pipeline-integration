"""add topics and document topic links

Revision ID: e3c5a6f91ab2
Revises: d9f7e328648f
Create Date: 2026-09-01 00:00:03.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3c5a6f91ab2"
down_revision: Union[str, Sequence[str], None] = "d9f7e328648f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "topics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_topics_id"), "topics", ["id"], unique=False)
    op.create_index(op.f("ix_topics_parent_id"), "topics", ["parent_id"], unique=False)
    op.create_index(op.f("ix_topics_user_id"), "topics", ["user_id"], unique=False)

    op.add_column("documents", sa.Column("topic_id", sa.Integer(), nullable=True))
    op.create_index(
        op.f("ix_documents_topic_id"),
        "documents",
        ["topic_id"],
        unique=False,
    )
    op.create_foreign_key(
        op.f("fk_documents_topic_id_topics"),
        "documents",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_foreign_key(
        op.f("fk_chunks_topic_id_topics"),
        "chunks",
        "topics",
        ["topic_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("fk_chunks_topic_id_topics"), "chunks", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_documents_topic_id_topics"),
        "documents",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_documents_topic_id"), table_name="documents")
    op.drop_column("documents", "topic_id")
    op.drop_index(op.f("ix_topics_user_id"), table_name="topics")
    op.drop_index(op.f("ix_topics_parent_id"), table_name="topics")
    op.drop_index(op.f("ix_topics_id"), table_name="topics")
    op.drop_table("topics")
