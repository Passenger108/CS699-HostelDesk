"""users and login

Revision ID: 2676e93242d2
Revises: 
Create Date: 2026-10-14 14:18:16.633948

"""
from alembic import op
import sqlalchemy as sa


revision = '2676e93242d2'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
    sa.Column('role', sa.Enum('STUDENT', 'WORKER', 'SUPERVISOR', 'SUPER_ADMIN', name='user_role'), nullable=False),
    sa.Column('login_id', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('phone', sa.String(length=20), nullable=True),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('locale', sa.Enum('en', 'hi', 'mr', name='user_locale'), nullable=False),
    sa.Column('avatar_key', sa.String(length=255), nullable=True),
    sa.Column('account_status', sa.Enum('ACTIVE', 'DISABLED', 'LOCKED', name='account_status'), nullable=False),
    sa.Column('failed_login_count', sa.Integer(), nullable=False),
    sa.Column('first_failed_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('token_version', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('login_id', name=op.f('uq_users_login_id'))
    )


def downgrade():
    op.drop_table('users')
    for name in ("user_role", "user_locale", "account_status"):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
