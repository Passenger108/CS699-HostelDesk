"""cleaning requests and request events

Revision ID: a94ba8778dab
Revises: 094cba4fd435
Create Date: 2026-10-17 04:32:48.252402

"""
from alembic import op
import sqlalchemy as sa


revision = 'a94ba8778dab'
down_revision = '094cba4fd435'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('cleaning_requests',
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('active_student_id', sa.Integer(), nullable=True),
    sa.Column('client_key', sa.String(length=64), nullable=True),
    sa.Column('room_id', sa.Integer(), nullable=False),
    sa.Column('room_snapshot', sa.JSON(), nullable=False),
    sa.Column('contact_phone', sa.String(length=20), nullable=False),
    sa.Column('status', sa.Enum('SUBMITTED', 'AWAITING_ASSIGNMENT', 'OFFERED', 'AWAITING_REASSIGNMENT', 'ACCEPTED_QUEUED', 'AWAITING_STUDENT_RESCHEDULE', 'EN_ROUTE', 'ARRIVED', 'CLEANING_IN_PROGRESS', 'AWAITING_STUDENT_CONFIRMATION', 'SUPERVISOR_INTERVENTION', 'DISPUTED', 'CLOSED_SUCCESSFUL', 'CLOSED_VALID_AFTER_REVIEW', 'CLOSED_UNSATISFACTORY', 'STUDENT_UNAVAILABLE', 'CANCELLED_BY_STUDENT', 'CANCELLED_BY_SUPERVISOR', 'EXPIRED', name='request_status'), nullable=False),
    sa.Column('priority', sa.Enum('NORMAL', 'URGENT', 'EMERGENCY', name='request_priority'), nullable=False),
    sa.Column('urgent_reason', sa.String(length=500), nullable=True),
    sa.Column('note', sa.String(length=500), nullable=True),
    sa.Column('availability_mode', sa.Enum('AVAILABLE_NOW', 'TIME_WINDOW', 'ANY_TIME_TODAY', name='availability_mode'), nullable=False),
    sa.Column('window_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('window_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('available_until', sa.DateTime(timezone=True), nullable=False),
    sa.Column('credit_reservation', sa.Enum('NONE', 'RESERVED', 'CONSUMED', 'RELEASED', name='credit_reservation'), nullable=False),
    sa.Column('assigned_worker_id', sa.Integer(), nullable=True),
    sa.Column('offered_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('original_eta_minutes', sa.Integer(), nullable=True),
    sa.Column('latest_eta_minutes', sa.Integer(), nullable=True),
    sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolution_reason', sa.String(length=500), nullable=True),
    sa.Column('lock_version', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['active_student_id'], ['users.id'], name=op.f('fk_cleaning_requests_active_student_id_users')),
    sa.ForeignKeyConstraint(['assigned_worker_id'], ['users.id'], name=op.f('fk_cleaning_requests_assigned_worker_id_users')),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], name=op.f('fk_cleaning_requests_room_id_rooms')),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], name=op.f('fk_cleaning_requests_student_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_cleaning_requests')),
    sa.UniqueConstraint('active_student_id', name=op.f('uq_cleaning_requests_active_student_id')),
    sa.UniqueConstraint('student_id', 'client_key', name='uq_cleaning_requests_client_key')
    )
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cleaning_requests_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_cleaning_requests_student_id'), ['student_id'], unique=False)

    op.create_table('request_events',
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('old_state', sa.Enum('SUBMITTED', 'AWAITING_ASSIGNMENT', 'OFFERED', 'AWAITING_REASSIGNMENT', 'ACCEPTED_QUEUED', 'AWAITING_STUDENT_RESCHEDULE', 'EN_ROUTE', 'ARRIVED', 'CLEANING_IN_PROGRESS', 'AWAITING_STUDENT_CONFIRMATION', 'SUPERVISOR_INTERVENTION', 'DISPUTED', 'CLOSED_SUCCESSFUL', 'CLOSED_VALID_AFTER_REVIEW', 'CLOSED_UNSATISFACTORY', 'STUDENT_UNAVAILABLE', 'CANCELLED_BY_STUDENT', 'CANCELLED_BY_SUPERVISOR', 'EXPIRED', name='request_status'), nullable=True),
    sa.Column('new_state', sa.Enum('SUBMITTED', 'AWAITING_ASSIGNMENT', 'OFFERED', 'AWAITING_REASSIGNMENT', 'ACCEPTED_QUEUED', 'AWAITING_STUDENT_RESCHEDULE', 'EN_ROUTE', 'ARRIVED', 'CLEANING_IN_PROGRESS', 'AWAITING_STUDENT_CONFIRMATION', 'SUPERVISOR_INTERVENTION', 'DISPUTED', 'CLOSED_SUCCESSFUL', 'CLOSED_VALID_AFTER_REVIEW', 'CLOSED_UNSATISFACTORY', 'STUDENT_UNAVAILABLE', 'CANCELLED_BY_STUDENT', 'CANCELLED_BY_SUPERVISOR', 'EXPIRED', name='request_status'), nullable=False),
    sa.Column('payload_json', sa.JSON(), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_request_events_actor_id_users')),
    sa.ForeignKeyConstraint(['request_id'], ['cleaning_requests.id'], name=op.f('fk_request_events_request_id_cleaning_requests')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_request_events'))
    )
    with op.batch_alter_table('request_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_request_events_request_id'), ['request_id'], unique=False)

    with op.batch_alter_table('credit_ledger', schema=None) as batch_op:
        batch_op.create_foreign_key(batch_op.f('fk_credit_ledger_request_id_cleaning_requests'), 'cleaning_requests', ['request_id'], ['id'])


def downgrade():
    with op.batch_alter_table('credit_ledger', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_credit_ledger_request_id_cleaning_requests'), type_='foreignkey')

    with op.batch_alter_table('request_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_request_events_request_id'))

    op.drop_table('request_events')
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cleaning_requests_student_id'))
        batch_op.drop_index(batch_op.f('ix_cleaning_requests_status'))

    op.drop_table('cleaning_requests')
    for name in ("request_status", "request_priority", "availability_mode", "credit_reservation"):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
