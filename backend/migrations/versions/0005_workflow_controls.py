"""Second-based targets and approved, resumable stage generation."""
from alembic import op
import sqlalchemy as sa

revision = "0005_workflow"
down_revision = "0004_animation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.alter_column("target_minutes", existing_type=sa.Integer(), type_=sa.Float(),
                           existing_nullable=False, existing_server_default="1")
        batch.add_column(sa.Column("generation_approval", sa.JSON(), nullable=False,
                                   server_default=sa.text("'{}'")))
    op.add_column("jobs", sa.Column("operation", sa.String(40), nullable=False, server_default="legacy_video"))
    op.add_column("jobs", sa.Column("snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))


def downgrade() -> None:
    # Round upward rather than silently truncating short, second-based targets.
    op.execute("UPDATE projects SET target_minutes = CAST(target_minutes AS INTEGER) + "
               "CASE WHEN target_minutes > CAST(target_minutes AS INTEGER) THEN 1 ELSE 0 END")
    op.drop_column("jobs", "snapshot")
    op.drop_column("jobs", "operation")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("generation_approval")
        batch.alter_column("target_minutes", existing_type=sa.Float(), type_=sa.Integer(),
                           existing_nullable=False, existing_server_default="1")
