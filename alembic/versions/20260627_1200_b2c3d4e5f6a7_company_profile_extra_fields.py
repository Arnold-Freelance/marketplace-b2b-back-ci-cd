"""profil entreprise : champs supplémentaires

Ajoute region, tax_id, phone, whatsapp, facebook, instagram à company_profiles
pour que l'écran d'édition du profil fournisseur persiste réellement ces champs.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-27 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('company_profiles', sa.Column('region', sa.String(length=100), nullable=True))
    op.add_column('company_profiles', sa.Column('tax_id', sa.String(length=100), nullable=True))
    op.add_column('company_profiles', sa.Column('phone', sa.String(length=30), nullable=True))
    op.add_column('company_profiles', sa.Column('whatsapp', sa.String(length=30), nullable=True))
    op.add_column('company_profiles', sa.Column('facebook', sa.String(length=255), nullable=True))
    op.add_column('company_profiles', sa.Column('instagram', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('company_profiles', 'instagram')
    op.drop_column('company_profiles', 'facebook')
    op.drop_column('company_profiles', 'whatsapp')
    op.drop_column('company_profiles', 'phone')
    op.drop_column('company_profiles', 'tax_id')
    op.drop_column('company_profiles', 'region')
