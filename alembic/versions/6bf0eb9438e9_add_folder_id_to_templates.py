"""add_folder_id_to_templates

Revision ID: 6bf0eb9438e9
Revises: 6a054832e6dc
Create Date: 2025-08-12 19:14:50.346117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6bf0eb9438e9'
down_revision: Union[str, None] = '6a054832e6dc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add folder_id column to templates table
    op.add_column('templates', sa.Column('folder_id', sa.String(), nullable=True))
    op.create_index('idx_template_folder_id', 'templates', ['folder_id'], unique=False)


def downgrade() -> None:
    # Remove folder_id column from templates table
    op.drop_index('idx_template_folder_id', table_name='templates')
    op.drop_column('templates', 'folder_id')
