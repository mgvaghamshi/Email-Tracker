"""add_recurring_campaigns_feature_to_plans

Revision ID: d956c5ac39a5
Revises: ab0936a16ad7
Create Date: 2025-08-22 14:22:23.518847

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd956c5ac39a5'
down_revision: Union[str, None] = 'ab0936a16ad7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
