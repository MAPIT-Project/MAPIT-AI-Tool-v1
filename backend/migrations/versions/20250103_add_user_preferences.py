"""Add user preferences table

Revision ID: 20250103_add_user_preferences
Revises: 20250102_add_confidence_column
Create Date: 2025-01-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250103_add_user_preferences'
down_revision = '20250102_add_confidence_column'
branch_labels = None
depends_on = None


def upgrade():
    # Create user_preferences table
    op.create_table('user_preferences',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('neo4j_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('qdrant_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('elasticsearch_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )
    
    # Create index on user_id
    op.create_index(op.f('ix_user_preferences_user_id'), 'user_preferences', ['user_id'], unique=False)


def downgrade():
    # Drop index
    op.drop_index(op.f('ix_user_preferences_user_id'), table_name='user_preferences')
    
    # Drop table
    op.drop_table('user_preferences')
