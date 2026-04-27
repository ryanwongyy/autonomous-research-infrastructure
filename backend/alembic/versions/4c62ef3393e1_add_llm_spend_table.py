"""add llm_spend table

Revision ID: 4c62ef3393e1
Revises: 6caa5fb6b874
Create Date: 2026-04-27 23:11:21.948168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4c62ef3393e1'
down_revision: Union[str, None] = '6caa5fb6b874'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_spend",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "paper_id",
            sa.String(length=64),
            sa.ForeignKey("papers.id"),
            nullable=True,
            index=True,
        ),
        sa.Column("role", sa.String(length=64), nullable=False, index=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        op.f("ix_llm_spend_paper_id"), "llm_spend", ["paper_id"], unique=False
    )
    op.create_index(op.f("ix_llm_spend_role"), "llm_spend", ["role"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_llm_spend_role"), table_name="llm_spend")
    op.drop_index(op.f("ix_llm_spend_paper_id"), table_name="llm_spend")
    op.drop_table("llm_spend")
