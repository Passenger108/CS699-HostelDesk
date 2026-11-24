"""worker queue position

Revision ID: 7ae8fd6d1a8d
Revises: 1e4499ce9843
Create Date: 2026-10-29 16:37:10.193793

"""
from alembic import op
import sqlalchemy as sa


revision = '7ae8fd6d1a8d'
down_revision = '1e4499ce9843'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('queue_position', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.drop_column('queue_position')
