"""credit ledger, settings and audit log

Revision ID: 094cba4fd435
Revises: b42191a69955
Create Date: 2026-10-15 19:24:44.329984

"""
from alembic import op
import sqlalchemy as sa


revision = '094cba4fd435'
down_revision = 'b42191a69955'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('audit_logs',
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('before_json', sa.JSON(), nullable=True),
    sa.Column('after_json', sa.JSON(), nullable=True),
    sa.Column('reason', sa.String(length=500), nullable=True),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_logs_actor_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_action'), ['action'], unique=False)

    op.create_table('credit_ledger',
    sa.Column('student_id', sa.Integer(), nullable=False),
    sa.Column('entry_type', sa.Enum('WEEKLY_GRANT', 'WEEKLY_CAPPED', 'GOODWILL_GRANT', 'RESERVE', 'RELEASE', 'CONSUME', 'EXPIRE', name='credit_entry_type'), nullable=False),
    sa.Column('credit_type', sa.Enum('STANDARD', 'GOODWILL', name='credit_type'), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('request_id', sa.Integer(), nullable=True),
    sa.Column('actor_id', sa.Integer(), nullable=True),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('grant_week', sa.Date(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_credit_ledger_actor_id_users')),
    sa.ForeignKeyConstraint(['student_id'], ['users.id'], name=op.f('fk_credit_ledger_student_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_credit_ledger')),
    sa.UniqueConstraint('student_id', 'grant_week', name=op.f('uq_credit_ledger_student_id'))
    )
    with op.batch_alter_table('credit_ledger', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_credit_ledger_request_id'), ['request_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_credit_ledger_student_id'), ['student_id'], unique=False)

    op.create_table('settings',
    sa.Column('key', sa.String(length=64), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('changed_by_id', sa.Integer(), nullable=True),
    sa.Column('reason', sa.String(length=500), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['changed_by_id'], ['users.id'], name=op.f('fk_settings_changed_by_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_settings')),
    sa.UniqueConstraint('key', 'version', name=op.f('uq_settings_key'))
    )


def downgrade():
    op.drop_table('settings')
    with op.batch_alter_table('credit_ledger', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_credit_ledger_student_id'))
        batch_op.drop_index(batch_op.f('ix_credit_ledger_request_id'))

    op.drop_table('credit_ledger')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_action'))

    op.drop_table('audit_logs')
    for name in ("credit_entry_type", "credit_type"):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
