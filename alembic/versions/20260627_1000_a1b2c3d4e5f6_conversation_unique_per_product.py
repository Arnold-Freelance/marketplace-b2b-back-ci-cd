"""conversation unique par produit

Ajoute product_id à la contrainte d'unicité des conversations pour que les
demandes sur des produits différents (même fournisseur) soient des fils
distincts.

Revision ID: a1b2c3d4e5f6
Revises: 66d459aaa676
Create Date: 2026-06-27 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '66d459aaa676'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('unique_conversation', 'conversations', type_='unique')
    op.create_unique_constraint(
        'unique_conversation',
        'conversations',
        ['buyer_id', 'supplier_id', 'order_id', 'product_id'],
    )


def downgrade() -> None:
    op.drop_constraint('unique_conversation', 'conversations', type_='unique')
    op.create_unique_constraint(
        'unique_conversation',
        'conversations',
        ['buyer_id', 'supplier_id', 'order_id'],
    )
