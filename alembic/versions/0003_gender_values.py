"""store gender as male/female instead of Chinese labels

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

students = sa.table("students", sa.column("gender", sa.String))

# Legacy Chinese labels (male / female) written by earlier versions
LEGACY_MALE = "\u7537"
LEGACY_FEMALE = "\u5973"


def upgrade() -> None:
    op.execute(students.update().where(students.c.gender == LEGACY_MALE).values(gender="male"))
    op.execute(students.update().where(students.c.gender == LEGACY_FEMALE).values(gender="female"))


def downgrade() -> None:
    op.execute(students.update().where(students.c.gender == "male").values(gender=LEGACY_MALE))
    op.execute(students.update().where(students.c.gender == "female").values(gender=LEGACY_FEMALE))
