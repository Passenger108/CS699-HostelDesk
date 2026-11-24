"""assignment offers

Revision ID: 1e4499ce9843
Revises: 5ba17276de24
Create Date: 2026-10-24 14:49:32.363468

"""
from alembic import op
import sqlalchemy as sa


revision = '1e4499ce9843'
down_revision = '5ba17276de24'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('assignment_offers',
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('worker_id', sa.Integer(), nullable=False),
    sa.Column('offered_by_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'ACCEPTED', 'DECLINED', 'TIMED_OUT', 'WITHDRAWN', name='offer_status'), nullable=False),
    sa.Column('response_deadline', sa.DateTime(timezone=True), nullable=False),
    sa.Column('explanation', sa.String(length=300), nullable=False),
    sa.Column('decline_reason', sa.String(length=500), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['offered_by_id'], ['users.id'], name=op.f('fk_assignment_offers_offered_by_id_users')),
    sa.ForeignKeyConstraint(['request_id'], ['cleaning_requests.id'], name=op.f('fk_assignment_offers_request_id_cleaning_requests')),
    sa.ForeignKeyConstraint(['worker_id'], ['users.id'], name=op.f('fk_assignment_offers_worker_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assignment_offers'))
    )
    with op.batch_alter_table('assignment_offers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_assignment_offers_request_id'), ['request_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_assignment_offers_worker_id'), ['worker_id'], unique=False)


def downgrade():
    with op.batch_alter_table('assignment_offers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_assignment_offers_worker_id'))
        batch_op.drop_index(batch_op.f('ix_assignment_offers_request_id'))

    op.drop_table('assignment_offers')
    sa.Enum(name='offer_status').drop(op.get_bind(), checkfirst=True)
