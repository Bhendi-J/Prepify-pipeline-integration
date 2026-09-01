"""allow variable chunk embedding dimensions

Revision ID: d9f7e328648f
Revises: c5ef9c0f0194
Create Date: 2026-09-01 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d9f7e328648f"
down_revision: Union[str, Sequence[str], None] = "c5ef9c0f0194"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TABLE chunks "
        "ALTER COLUMN embedding TYPE vector "
        "USING embedding::vector"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM chunks
                WHERE vector_dims(embedding) <> 1536
            ) THEN
                RAISE EXCEPTION
                    'Cannot downgrade chunks.embedding to vector(1536) while non-1536 embeddings exist';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        "ALTER TABLE chunks "
        "ALTER COLUMN embedding TYPE vector(1536) "
        "USING embedding::vector(1536)"
    )
