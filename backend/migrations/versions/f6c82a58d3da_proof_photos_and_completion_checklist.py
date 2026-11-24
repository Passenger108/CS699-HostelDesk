"""proof photos and completion checklist

Revision ID: f6c82a58d3da
Revises: f581a8ea12b8
Create Date: 2026-11-14 22:24:20.069130

"""
from alembic import op
import sqlalchemy as sa


revision = 'f6c82a58d3da'
down_revision = 'f581a8ea12b8'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('proof_photos',
    sa.Column('request_id', sa.Integer(), nullable=False),
    sa.Column('uploaded_by_id', sa.Integer(), nullable=False),
    sa.Column('storage_key', sa.String(length=80), nullable=False),
    sa.Column('content_type', sa.String(length=40), nullable=False),
    sa.Column('size_bytes', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['cleaning_requests.id'], name=op.f('fk_proof_photos_request_id_cleaning_requests')),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], name=op.f('fk_proof_photos_uploaded_by_id_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_proof_photos')),
    sa.UniqueConstraint('storage_key', name=op.f('uq_proof_photos_storage_key'))
    )
    with op.batch_alter_table('proof_photos', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_proof_photos_request_id'), ['request_id'], unique=False)

    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('checklist', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('confirm_deadline', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('cleaning_requests', schema=None) as batch_op:
        batch_op.drop_column('confirm_deadline')
        batch_op.drop_column('checklist')

    with op.batch_alter_table('proof_photos', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_proof_photos_request_id'))

    op.drop_table('proof_photos')
