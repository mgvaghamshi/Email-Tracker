"""merge_heads

Revision ID: ab0936a16ad7
Revises: c8ad14760adf, unified_campaign_001
Create Date: 2025-08-22 14:22:08.307035

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab0936a16ad7'
down_revision: Union[str, None] = ('c8ad14760adf', 'unified_campaign_001')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
