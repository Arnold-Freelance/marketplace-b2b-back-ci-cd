"""rôles multiples : table user_roles + migration de données (T5)

Introduit une liste de rôles par utilisateur (buyer/supplier/admin). Migre les
comptes existants : chaque user reçoit un rôle = son `user_type` courant ; tout
`supplier` reçoit **aussi** `buyer` (un vendeur est aussi acheteur).

La colonne legacy `users.user_type` est conservée (compat mobile non migré).

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-07 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table des rôles
    op.create_table(
        'user_roles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'role', name='uq_user_roles_user_role'),
    )
    op.create_index('ix_user_roles_user_id', 'user_roles', ['user_id'])

    # 2. Migration de données : rôle courant pour tous les comptes existants.
    op.execute(
        """
        INSERT INTO user_roles (user_id, role, created_at)
        SELECT id, user_type::text, now()
        FROM users
        """
    )
    # 3. Tout supplier obtient aussi le rôle buyer.
    op.execute(
        """
        INSERT INTO user_roles (user_id, role, created_at)
        SELECT u.id, 'buyer', now()
        FROM users u
        WHERE u.user_type::text = 'supplier'
          AND NOT EXISTS (
              SELECT 1 FROM user_roles r
              WHERE r.user_id = u.id AND r.role = 'buyer'
          )
        """
    )


def downgrade() -> None:
    op.drop_index('ix_user_roles_user_id', table_name='user_roles')
    op.drop_table('user_roles')
