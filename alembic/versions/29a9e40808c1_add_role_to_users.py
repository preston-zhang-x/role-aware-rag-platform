"""add role to users

Revision ID: 29a9e40808c1
Revises: d3357c3b484c
Create Date: 2026-03-07 22:24:49.680498
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "29a9e40808c1"
down_revision: Union[str, None] = "d3357c3b484c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


user_role_enum = sa.Enum(
    "ADMIN",
    "EDITOR",
    "VIEWER",
    name="user_role",
    native_enum=False,
)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            user_role_enum,
            nullable=False,
            server_default="VIEWER",
        ),
    )
    op.alter_column("users", "role", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "role")
