"""Add context_sources column to messages table

Revision ID: 20250103_add_context_sources_column
Revises: 20250102_add_confidence_column
Create Date: 2025-01-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250103_context_sources'
down_revision = '20250102_add_confidence_column'
branch_labels = None
depends_on = None


def upgrade():
    # Add context_sources column to messages table
    op.add_column('messages', sa.Column('context_sources', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade():
    # Remove context_sources column from messages table
    op.drop_column('messages', 'context_sources')
