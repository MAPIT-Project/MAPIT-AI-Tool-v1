"""Add confidence column to messages table

Revision ID: 20250102_add_confidence_column
Revises: 20250101_add_related_links_column
Create Date: 2025-01-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250102_add_confidence_column'
down_revision = '20250101_add_related_links_column'
branch_labels = None
depends_on = None


def upgrade():
    # Add confidence column to messages table
    op.add_column('messages', sa.Column('confidence', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade():
    # Remove confidence column from messages table
    op.drop_column('messages', 'confidence') 