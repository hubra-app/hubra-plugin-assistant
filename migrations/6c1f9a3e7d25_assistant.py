"""assistant drafts

Runs in public and in every club's schema, tracked in its own version table
(alembic_version_assistant). has_table() keeps it safe to run twice.

Revision ID: 6c1f9a3e7d25
Revises:
Create Date: 2026-11-05 16:00:00

"""

from alembic import op
import sqlalchemy as sa

from hubra.core.plugins.ops import has_table

revision = "6c1f9a3e7d25"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    if not has_table("assistant_drafts"):
        op.create_table(
            "assistant_drafts",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(12), nullable=False),
            sa.Column("language", sa.String(5), nullable=False),
            sa.Column("notes", sa.Text(), nullable=False),
            sa.Column("event_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(300), nullable=True),
            sa.Column("body", sa.Text(), nullable=True),
            sa.Column("model", sa.String(40), nullable=False),
            sa.Column("input_tokens", sa.Integer(), nullable=False),
            sa.Column("output_tokens", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["event_id"], ["club_events.id"], ondelete="SET NULL"
            ),
            sa.ForeignKeyConstraint(
                ["created_by"], ["members.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_assistant_drafts_created_by", "assistant_drafts", ["created_by"]
        )


def downgrade():
    if has_table("assistant_drafts"):
        op.drop_table("assistant_drafts")
