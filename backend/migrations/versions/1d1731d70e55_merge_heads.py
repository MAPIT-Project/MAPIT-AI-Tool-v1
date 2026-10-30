"""merge heads

Revision ID: 1d1731d70e55
Revises: 20250103_context_sources, 20250103_add_user_preferences
Create Date: 2025-08-20 08:13:32.269442

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1d1731d70e55'
down_revision = ('20250103_context_sources', '20250103_add_user_preferences')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
