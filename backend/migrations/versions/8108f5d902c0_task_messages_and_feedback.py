"""task messages and feedback

Revision ID: 8108f5d902c0
Revises: f6c82a58d3da
Create Date: 2026-11-21 15:13:16.921863

"""
from alembic import op
import sqlalchemy as sa


revision = '8108f5d902c0'
down_revision = 'f6c82a58d3da'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('feedback',
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('worker_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.String(length=500), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['cleaning_requests.id'], name=op.f('fk_feedback_request_id_cleaning_requests')),
    sa.ForeignKeyConstraint(['worker_id'], ['users.id'], name=op.f('fk_feedback_worker_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_feedback')),
    sa.UniqueConstraint('request_id', name=op.f('uq_feedback_request_id'))
    )
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_feedback_worker_id'), ['worker_id'], unique=False)

    op.create_table('task_messages',
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('body', sa.String(length=500), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['cleaning_requests.id'], name=op.f('fk_task_messages_request_id_cleaning_requests')),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], name=op.f('fk_task_messages_sender_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_task_messages'))
    )
    with op.batch_alter_table('task_messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_messages_request_id'), ['request_id'], unique=False)


def downgrade():
    with op.batch_alter_table('task_messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_task_messages_request_id'))

    op.drop_table('task_messages')
    with op.batch_alter_table('feedback', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_feedback_worker_id'))

    op.drop_table('feedback')
