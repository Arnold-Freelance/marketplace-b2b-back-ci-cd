"""addresses book

Carnet d'adresses de livraison réutilisables (une par défaut à la fois).

Revision ID: 2e9237723777
Revises: 75c052ab50d3
Create Date: 2026-07-14 14:59:37.355187
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '2e9237723777'
down_revision: Union[str, None] = '75c052ab50d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('address_line1', sa.String(length=255), nullable=False),
        sa.Column('address_line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=100), server_default="Côte d'Ivoire", nullable=False),
        sa.Column('landmark', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('is_deleted', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_addresses_id'), 'addresses', ['id'], unique=False)
    op.create_index(op.f('ix_addresses_user_id'), 'addresses', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_addresses_user_id'), table_name='addresses')
    op.drop_index(op.f('ix_addresses_id'), table_name='addresses')
    op.drop_table('addresses')
