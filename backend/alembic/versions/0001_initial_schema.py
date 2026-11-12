"""Initial schema for Knowledge Handover Platform with pgvector support.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-11-12
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from app.models.entities import EmbeddingVectorType

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create all declared tables via SQLAlchemy metadata for clean cross-dialect parity
    from app.core.database import Base
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    from app.core.database import Base
    Base.metadata.drop_all(bind=bind)
