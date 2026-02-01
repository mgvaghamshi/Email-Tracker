"""update_recurring_campaigns_schema

Revision ID: 58619256db3c
Revises: d956c5ac39a5
Create Date: 2025-08-22 14:53:32.666727

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58619256db3c'
down_revision: Union[str, None] = 'd956c5ac39a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
