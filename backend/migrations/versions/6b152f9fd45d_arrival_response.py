"""arrival response

Revision ID: 6b152f9fd45d
Revises: 7ae8fd6d1a8d
Create Date: 2026-11-03 17:36:02.515067

"""
from alembic import op
import sqlalchemy as sa


revision = '6b152f9fd45d'
down_revision = '7ae8fd6d1a8d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('arrival_response', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('response_deadline', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.drop_column('response_deadline')
        batch_op.drop_column('arrival_response')
