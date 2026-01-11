"""Create ai_jobs table (async jobs)

Revision ID: 20260108_0001
Revises: 
Create Date: 2026-01-08
"""

from alembic import op
import sqlalchemy as sa

revision = "20260108_0001"
down_revision = None
branch_labels = None
depends_on = None


def _enum_type_exists(conn, name: str) -> bool:
    try:
        res = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = :n"), {"n": name}).fetchone()
        return bool(res)
    except Exception:
        return False


def upgrade() -> None:
    conn = op.get_bind()

    # Create enum type if missing (postgres)
    enum_name = "aijobstatus"
    if conn.dialect.name == "postgresql" and not _enum_type_exists(conn, enum_name):
        sa.Enum("queued", "running", "succeeded", "failed", name=enum_name).create(conn, checkfirst=False)

    # Create table if missing
    inspector = sa.inspect(conn)
    if "ai_jobs" in inspector.get_table_names():
        return

    status_enum = sa.Enum("queued", "running", "succeeded", "failed", name=enum_name) if conn.dialect.name == "postgresql" else sa.Enum("queued", "running", "succeeded", "failed")

    op.create_table(
        "ai_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", status_enum, nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("error_detail", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    op.create_index("idx_ai_jobs_project_id", "ai_jobs", ["project_id"])
    op.create_index("idx_ai_jobs_status", "ai_jobs", ["status"])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    if "ai_jobs" in inspector.get_table_names():
        op.drop_index("idx_ai_jobs_status", table_name="ai_jobs")
        op.drop_index("idx_ai_jobs_project_id", table_name="ai_jobs")
        op.drop_table("ai_jobs")

    if conn.dialect.name == "postgresql":
        enum_name = "aijobstatus"
        if _enum_type_exists(conn, enum_name):
            sa.Enum("queued", "running", "succeeded", "failed", name=enum_name).drop(conn, checkfirst=False)

