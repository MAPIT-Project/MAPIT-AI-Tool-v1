"""Add user_id columns to chat_sessions and messages tables

Revision ID: add_user_id_columns
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_user_id_columns'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add user_id column to chat_sessions table
    op.add_column('chat_sessions', sa.Column('user_id', sa.String(255), nullable=True))
    op.create_index(op.f('ix_chat_sessions_user_id'), 'chat_sessions', ['user_id'], unique=False)
    
    # Add user_id column to messages table
    op.add_column('messages', sa.Column('user_id', sa.String(255), nullable=True))
    op.create_index(op.f('ix_messages_user_id'), 'messages', ['user_id'], unique=False)
    
    # Update existing records with a default user_id (for backward compatibility)
    # This will be handled by the application logic


def downgrade():
    # Remove indexes
    op.drop_index(op.f('ix_messages_user_id'), table_name='messages')
    op.drop_index(op.f('ix_chat_sessions_user_id'), table_name='chat_sessions')
    
    # Remove columns
    op.drop_column('messages', 'user_id')
    op.drop_column('chat_sessions', 'user_id') 