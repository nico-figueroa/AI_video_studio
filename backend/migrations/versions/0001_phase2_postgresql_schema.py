"""Create Phase 2 PostgreSQL schema.

Revision ID: 0001_phase2
Revises:
Create Date: 2026-11-05
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001_phase2"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False, server_default="Untitled project"),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("story_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("genre", sa.String(120), nullable=False, server_default=""),
        sa.Column("target_audience", sa.String(240), nullable=False, server_default=""),
        sa.Column("three_act_structure", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("status", sa.String(40), nullable=False, server_default="created"),
        sa.Column("target_minutes", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("max_budget", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("max_wait_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("selected_plan", sa.String(20), nullable=True),
        sa.Column("video_path", sa.String(500), nullable=True),
        sa.Column("actual_cost", sa.Float(), nullable=False, server_default="0"),
        sa.Column("estimated_spend", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "ai_configuration",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(120), nullable=False, server_default="gpt-5"),
        sa.Column("image_model", sa.String(120), nullable=False, server_default="gpt-image-1"),
        sa.Column("default_budget", sa.Float(), nullable=False, server_default="5.0"),
        sa.Column("default_wait_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default=""),
        sa.Column("personality", sa.Text(), nullable=False, server_default=""),
        sa.Column("appearance", sa.Text(), nullable=False, server_default=""),
        sa.Column("motivations", sa.Text(), nullable=False, server_default=""),
        sa.Column("relationships", sa.Text(), nullable=False, server_default=""),
        sa.Column("portrait_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_characters_project_id", "characters", ["project_id"])
    op.create_table(
        "scenes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("scene_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("visual_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_prompt", sa.Text(), nullable=False, server_default=""),
        sa.Column("estimated_duration", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("image_path", sa.String(500), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("project_id", "scene_number", name="uq_scenes_project_number"),
    )
    op.create_index("ix_scenes_project_id", "scenes", ["project_id"])
    op.create_table(
        "estimates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("plan_name", sa.String(20), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("resolution", sa.String(30), nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=False),
        sa.Column("storage_mb", sa.Float(), nullable=False),
        sa.Column("gpu_minutes", sa.Float(), nullable=False),
    )
    op.create_index("ix_estimates_project_id", "estimates", ["project_id"])
    op.create_table(
        "generated_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("asset_type", sa.String(40), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_generated_assets_project_id", "generated_assets", ["project_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("current_stage", sa.String(60), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    dialect = op.get_context().dialect.name
    active_filter = sa.text("status IN ('queued', 'running')")
    index_options = (
        {"sqlite_where": active_filter}
        if dialect == "sqlite"
        else {"postgresql_where": active_filter}
    )
    op.create_index(
        "uq_jobs_active_project",
        "jobs",
        ["project_id"],
        unique=True,
        **index_options,
    )


def downgrade() -> None:
    op.drop_index("uq_jobs_active_project", table_name="jobs")
    op.drop_index("ix_jobs_project_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_generated_assets_project_id", table_name="generated_assets")
    op.drop_table("generated_assets")
    op.drop_index("ix_estimates_project_id", table_name="estimates")
    op.drop_table("estimates")
    op.drop_index("ix_scenes_project_id", table_name="scenes")
    op.drop_table("scenes")
    op.drop_index("ix_characters_project_id", table_name="characters")
    op.drop_table("characters")
    op.drop_table("ai_configuration")
    op.drop_table("projects")
