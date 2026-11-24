"""notifications

Revision ID: 5ba17276de24
Revises: a94ba8778dab
Create Date: 2026-10-20 05:47:19.097038

"""
from alembic import op
import sqlalchemy as sa


revision = '5ba17276de24'
down_revision = 'a94ba8778dab'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notifications',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=64), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index('ix_notifications_user_id_read_at', ['user_id', 'read_at'], unique=False)


def downgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index('ix_notifications_user_id_read_at')

    op.drop_table('notifications')
