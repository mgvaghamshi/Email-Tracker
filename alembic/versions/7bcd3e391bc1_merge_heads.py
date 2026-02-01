"""Merge heads

Revision ID: 7bcd3e391bc1
Revises: 9e049f3c48f7, defaults_management_001
Create Date: 2025-08-20 16:35:01.234968

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7bcd3e391bc1'
down_revision: Union[str, None] = ('9e049f3c48f7', 'defaults_management_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
