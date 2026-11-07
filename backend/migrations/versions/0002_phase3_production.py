"""Add narration, render checkpoints, and published video metadata."""

from alembic import op
import sqlalchemy as sa

revision = "0002_phase3"
down_revision = "0001_phase2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "narrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scene_id", sa.Integer(), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("recommended_seconds", sa.Float(), nullable=False),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("audio_path", sa.String(500)),
        sa.Column("audio_seconds", sa.Float()),
        sa.Column("speech_model", sa.String(120)),
        sa.Column("voice", sa.String(120)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_narrations_project_id", "narrations", ["project_id"])
    op.create_table(
        "render_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("current_stage", sa.String(60), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("timeline_hash", sa.String(64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("completed_scenes", sa.JSON(), nullable=False),
        sa.Column("execution_seconds", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_render_jobs_project_id", "render_jobs", ["project_id"])
    op.create_index(
        "uq_render_jobs_active_project", "render_jobs", ["project_id"], unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    op.create_table(
        "videos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("render_job_id", sa.String(36), sa.ForeignKey("render_jobs.id"), nullable=False, unique=True),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("audio_seconds", sa.Float(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("generation_seconds", sa.Float(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_videos_project_id", "videos", ["project_id"])


def downgrade() -> None:
    op.drop_table("videos")
    op.drop_table("render_jobs")
    op.drop_table("narrations")
