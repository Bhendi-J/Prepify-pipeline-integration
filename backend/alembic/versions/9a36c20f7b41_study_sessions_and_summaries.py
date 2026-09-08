"""Store study sessions and document summaries; preserve existing questions."""
from alembic import op
import sqlalchemy as sa

revision = "9a36c20f7b41"
down_revision = "8d92f0a63b17"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "study_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topic_id", sa.Integer(), sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("focus", sa.Text()),
        sa.Column("difficulty", sa.String(50), nullable=False),
        sa.Column("question_type", sa.String(50), nullable=False),
        sa.Column("request_id", sa.Uuid()),
        sa.Column("is_legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "request_id", name="uq_study_session_request"),
    )
    op.create_index("ix_study_sessions_user_id", "study_sessions", ["user_id"])
    op.create_index("ix_study_sessions_topic_id", "study_sessions", ["topic_id"])
    op.add_column("questions", sa.Column("session_id", sa.Integer(), sa.ForeignKey("study_sessions.id", ondelete="SET NULL")))
    op.create_index("ix_questions_session_id", "questions", ["session_id"])
    op.add_column("documents", sa.Column("summary_text", sa.Text()))
    op.add_column("documents", sa.Column("summary_status", sa.String(50), nullable=False, server_default="none"))
    op.execute("""
        INSERT INTO study_sessions (user_id, topic_id, title, difficulty, question_type, is_legacy, created_at)
        SELECT t.user_id, t.id, 'Earlier questions', 'mixed', 'mixed', true, min(q.created_at)
        FROM topics t JOIN questions q ON q.topic_id = t.id GROUP BY t.user_id, t.id
    """)
    op.execute("""
        UPDATE questions q SET session_id = s.id FROM study_sessions s
        WHERE q.topic_id = s.topic_id AND s.is_legacy = true AND q.session_id IS NULL
    """)


def downgrade():
    op.drop_column("documents", "summary_status")
    op.drop_column("documents", "summary_text")
    op.drop_index("ix_questions_session_id", table_name="questions")
    op.drop_column("questions", "session_id")
    op.drop_table("study_sessions")
