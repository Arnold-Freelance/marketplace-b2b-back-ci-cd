"""notifications push : device_tokens + notifications.event_key (T8)

Support des notifications hors-app (cf. NOTIFICATIONS_V1.md §4.1).

`device_tokens.token` est unique au niveau global, pas par utilisateur : un appareil
qui change de compte voit sa ligne réassignée au nouveau `user_id`. Sans cette
unicité, deux lignes coexisteraient et l'ancien propriétaire continuerait de
recevoir les notifications du nouveau.

`notifications.event_key` porte l'idempotence (règle §7.5) : la contrainte unique
`(user_id, event_key)` garantit qu'un retry ne crée pas de doublon, y compris sous
concurrence. Les `event_key` NULL ne collisionnent pas entre eux.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-10 15:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


push_provider_enum = sa.Enum('EXPO', 'FCM', name='pushprovider')
device_platform_enum = sa.Enum('ANDROID', 'IOS', name='deviceplatform')

# Les types sont créés explicitement dans upgrade(). Sans `create_type=False`,
# `create_table` tenterait de les recréer → DuplicateObject.
push_provider_col = postgresql.ENUM('EXPO', 'FCM', name='pushprovider', create_type=False)
device_platform_col = postgresql.ENUM('ANDROID', 'IOS', name='deviceplatform', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    push_provider_enum.create(bind, checkfirst=True)
    device_platform_enum.create(bind, checkfirst=True)

    op.create_table(
        'device_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('provider', push_provider_col, nullable=False, server_default='EXPO'),
        sa.Column('platform', device_platform_col, nullable=False),
        sa.Column('device_id', sa.String(length=128), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_device_tokens_id'), 'device_tokens', ['id'])
    op.create_index(op.f('ix_device_tokens_user_id'), 'device_tokens', ['user_id'])
    op.create_index(op.f('ix_device_tokens_token'), 'device_tokens', ['token'], unique=True)
    op.create_index(op.f('ix_device_tokens_device_id'), 'device_tokens', ['device_id'])
    op.create_index(op.f('ix_device_tokens_is_active'), 'device_tokens', ['is_active'])

    op.add_column('notifications', sa.Column('event_key', sa.String(length=120), nullable=True))
    op.create_index(op.f('ix_notifications_event_key'), 'notifications', ['event_key'])
    op.create_unique_constraint(
        'uq_notifications_user_event_key', 'notifications', ['user_id', 'event_key']
    )


def downgrade() -> None:
    op.drop_constraint('uq_notifications_user_event_key', 'notifications', type_='unique')
    op.drop_index(op.f('ix_notifications_event_key'), table_name='notifications')
    op.drop_column('notifications', 'event_key')

    op.drop_index(op.f('ix_device_tokens_is_active'), table_name='device_tokens')
    op.drop_index(op.f('ix_device_tokens_device_id'), table_name='device_tokens')
    op.drop_index(op.f('ix_device_tokens_token'), table_name='device_tokens')
    op.drop_index(op.f('ix_device_tokens_user_id'), table_name='device_tokens')
    op.drop_index(op.f('ix_device_tokens_id'), table_name='device_tokens')
    op.drop_table('device_tokens')

    bind = op.get_bind()
    device_platform_enum.drop(bind, checkfirst=True)
    push_provider_enum.drop(bind, checkfirst=True)
