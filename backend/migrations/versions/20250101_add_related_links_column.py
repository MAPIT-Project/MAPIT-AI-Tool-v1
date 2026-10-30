"""Add related_links column to messages table

Revision ID: 20250101_add_related_links_column
Revises: add_user_id_columns
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250101_add_related_links_column'
down_revision = 'add_user_id_columns'
branch_labels = None
depends_on = None


def upgrade():
    # Add related_links column to messages table
    op.add_column('messages', sa.Column('related_links', postgresql.JSON(astext_type=sa.Text()), nullable=True))


def downgrade():
    # Remove related_links column from messages table
    op.drop_column('messages', 'related_links') 