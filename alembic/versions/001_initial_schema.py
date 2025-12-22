"""Initial schema with pgvector and memory tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "metadata_",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index(
        "ix_sessions_metadata__gin",
        "sessions",
        ["metadata_"],
        postgresql_using="gin",
    )

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "role",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column(
            "metadata_",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.CheckConstraint("role IN ('user','assistant','system')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index(
        "ix_messages_metadata__gin",
        "messages",
        ["metadata_"],
        postgresql_using="gin",
    )

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column(
            "metadata_",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_documents_created_at", "documents", ["created_at"])
    op.create_index(
        "ix_documents_metadata__gin",
        "documents",
        ["metadata_"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_documents_embedding_hnsw",
        "documents",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )


def downgrade() -> None:
    op.drop_index("idx_documents_embedding_hnsw", table_name="documents")
    op.drop_index("ix_documents_metadata__gin", table_name="documents")
    op.drop_index("ix_documents_created_at", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_messages_metadata__gin", table_name="messages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_session_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_sessions_metadata__gin", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")

    op.execute("DROP EXTENSION IF EXISTS vector CASCADE")

