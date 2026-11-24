"""drop guardian contact

Revision ID: e08235fc4eb8
Revises: 8108f5d902c0
Create Date: 2026-11-24 02:11:39.447799

"""
from alembic import op
import sqlalchemy as sa


revision = 'e08235fc4eb8'
down_revision = '8108f5d902c0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('student_profiles', schema=None) as batch_op:
        batch_op.drop_column('guardian_contact')


def downgrade():
    with op.batch_alter_table('student_profiles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('guardian_contact', sa.VARCHAR(length=120), nullable=True))
