"""Initial migration

Revision ID: a36839204b48
Revises: 
Create Date: 2026-06-14 18:29:41.240843

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'a36839204b48'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
