"""add provenance_proof_json to source_snapshots

Revision ID: 6caa5fb6b874
Revises: cdef8b8f700b
Create Date: 2026-04-27 22:39:56.790328

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6caa5fb6b874'
down_revision: Union[str, None] = 'cdef8b8f700b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "source_snapshots",
        sa.Column("provenance_proof_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_snapshots", "provenance_proof_json")
