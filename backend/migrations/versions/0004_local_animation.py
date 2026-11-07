"""Persist isolated local GPU jobs and scene-clip review."""
from alembic import op
import sqlalchemy as sa

revision = "0004_animation"
down_revision = "0003_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("narrative_analysis", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("characters", sa.Column("facial_features", sa.Text(), nullable=False, server_default=""))
    op.add_column("scenes", sa.Column("beat_number", sa.Integer(), nullable=False, server_default="1"))
    op.create_table(
        "animation_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scene_id", sa.Integer(), sa.ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gpu_slot", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("result_metadata", sa.JSON(), nullable=False),
        sa.Column("clip_path", sa.String(500), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_animation_jobs_project_id", "animation_jobs", ["project_id"])
    op.create_index("ix_animation_jobs_scene_id", "animation_jobs", ["scene_id"])
    op.create_index(
        "uq_animation_gpu_active", "animation_jobs", ["gpu_slot"], unique=True,
        sqlite_where=sa.text("status IN ('queued', 'running')"),
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_table("animation_jobs")
    op.drop_column("scenes", "beat_number")
    op.drop_column("characters", "facial_features")
    op.drop_column("projects", "narrative_analysis")
