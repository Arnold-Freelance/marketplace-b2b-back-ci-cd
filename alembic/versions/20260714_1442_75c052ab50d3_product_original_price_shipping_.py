"""product original_price + shipping overrides

Prix de référence (prix barré) et barème de livraison par fournisseur.

Note : l'autogénération proposait aussi `drop_table('spatial_ref_sys')` (table
système PostGIS, absente des modèles) et le retrait des `server_default` de
`device_tokens`. Les deux ont été écartés — le premier casserait l'extension,
le second est une dérive sans rapport avec ce changement.

Revision ID: 75c052ab50d3
Revises: e5f6a7b8c9d0
Create Date: 2026-07-14 14:42:03.451982
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '75c052ab50d3'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Prix de référence avant remise. Nul = pas de promotion.
    op.add_column(
        'products',
        sa.Column('original_price', sa.Numeric(precision=10, scale=2), nullable=True),
    )
    # Surcharge de livraison pour un produit hors norme.
    op.add_column(
        'products',
        sa.Column('shipping_cost_override', sa.Numeric(precision=10, scale=2), nullable=True),
    )

    # Barème de livraison du fournisseur. `server_default='0'` : les profils
    # existants deviennent « livraison gratuite » plutôt que NULL — le calcul
    # n'a alors aucun cas indéfini à traiter.
    op.add_column(
        'company_profiles',
        sa.Column(
            'shipping_base_cost',
            sa.Numeric(precision=10, scale=2),
            server_default='0',
            nullable=False,
        ),
    )
    # Franco de port. Nul = pas de franco.
    op.add_column(
        'company_profiles',
        sa.Column('free_shipping_threshold', sa.Numeric(precision=12, scale=2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('company_profiles', 'free_shipping_threshold')
    op.drop_column('company_profiles', 'shipping_base_cost')
    op.drop_column('products', 'shipping_cost_override')
    op.drop_column('products', 'original_price')
