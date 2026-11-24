"""delay state and reschedule deadline

Revision ID: f581a8ea12b8
Revises: 6b152f9fd45d
Create Date: 2026-11-08 13:12:37.294307

"""
from alembic import op
import sqlalchemy as sa


revision = 'f581a8ea12b8'
down_revision = '6b152f9fd45d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('delay_state', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('reschedule_deadline', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.drop_column('reschedule_deadline')
        batch_op.drop_column('delay_state')
