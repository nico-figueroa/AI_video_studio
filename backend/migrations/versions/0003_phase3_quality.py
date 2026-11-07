"""Quality, continuity, adaptive-input provenance and review metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0003_quality"
down_revision = "0002_phase3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("story_approved", sa.Boolean(), nullable=False, server_default=sa.false()))
    for name in ("input_manifest", "narration_arc"):
        op.add_column("projects", sa.Column(name, sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("projects", sa.Column("review_overrides", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    for name in ("clothing", "distinctive_traits", "negative_prompt"):
        op.add_column("characters", sa.Column(name, sa.Text(), nullable=False, server_default=""))
    op.add_column("characters", sa.Column("age", sa.String(120), nullable=False, server_default=""))
    op.add_column("characters", sa.Column("reference_image_paths", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("characters", sa.Column("generation_context", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    for name in ("motion_plan", "generation_context"):
        op.add_column("scenes", sa.Column(name, sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("narrations", sa.Column("transition_text", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("narrations", "transition_text")
    for name in ("motion_plan", "generation_context"):
        op.drop_column("scenes", name)
    for name in ("clothing", "age", "distinctive_traits", "negative_prompt", "reference_image_paths", "generation_context"):
        op.drop_column("characters", name)
    for name in ("story_approved", "input_manifest", "narration_arc", "review_overrides"):
        op.drop_column("projects", name)
