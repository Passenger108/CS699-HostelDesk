"""hostel structure and profiles

Revision ID: b42191a69955
Revises: 2676e93242d2
Create Date: 2026-10-14 16:57:48.287109

"""
from alembic import op
import sqlalchemy as sa


revision = 'b42191a69955'
down_revision = '2676e93242d2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('hostels',
    sa.Column('code', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_hostels')),
    sa.UniqueConstraint('code', name=op.f('uq_hostels_code'))
    )
    op.create_table('floors',
    sa.Column('hostel_id', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['hostel_id'], ['hostels.id'], name=op.f('fk_floors_hostel_id_hostels')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_floors')),
    sa.UniqueConstraint('hostel_id', 'number', name=op.f('uq_floors_hostel_id'))
    )
    op.create_table('wings',
    sa.Column('floor_id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=4), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], name=op.f('fk_wings_floor_id_floors')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_wings')),
    sa.UniqueConstraint('floor_id', 'code', name=op.f('uq_wings_floor_id'))
    )
    op.create_table('locations',
    sa.Column('hostel_id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.Enum('FLOOR_WING', 'GROUND_FACILITY', name='location_kind'), nullable=False),
    sa.Column('floor_id', sa.Integer(), nullable=False),
    sa.Column('wing_id', sa.Integer(), nullable=True),
    sa.Column('facility_name', sa.String(length=80), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], name=op.f('fk_locations_floor_id_floors')),
    sa.ForeignKeyConstraint(['hostel_id'], ['hostels.id'], name=op.f('fk_locations_hostel_id_hostels')),
    sa.ForeignKeyConstraint(['wing_id'], ['wings.id'], name=op.f('fk_locations_wing_id_wings')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_locations'))
    )
    op.create_table('rooms',
    sa.Column('wing_id', sa.Integer(), nullable=False),
    sa.Column('number', sa.String(length=16), nullable=False),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['wing_id'], ['wings.id'], name=op.f('fk_rooms_wing_id_wings')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rooms')),
    sa.UniqueConstraint('wing_id', 'number', name=op.f('uq_rooms_wing_id'))
    )
    op.create_table('student_profiles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('roll_number', sa.String(length=32), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=False),
    sa.Column('guardian_contact', sa.String(length=120), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], name=op.f('fk_student_profiles_room_id_rooms')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_student_profiles_user_id_users')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_student_profiles')),
    sa.UniqueConstraint('roll_number', name=op.f('uq_student_profiles_roll_number'))
    )
    op.create_table('worker_profiles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.String(length=32), nullable=False),
    sa.Column('shift', sa.String(length=40), nullable=True),
    sa.Column('availability', sa.Enum('AVAILABLE', 'BUSY', 'OFF_DUTY', name='worker_availability'), nullable=False),
    sa.Column('last_location_id', sa.Integer(), nullable=True),
    sa.Column('location_updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('off_duty_requested_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['last_location_id'], ['locations.id'], name=op.f('fk_worker_profiles_last_location_id_locations')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_worker_profiles_user_id_users')),
    sa.PrimaryKeyConstraint('user_id', name=op.f('pk_worker_profiles')),
    sa.UniqueConstraint('employee_id', name=op.f('uq_worker_profiles_employee_id'))
    )


def downgrade():
    op.drop_table('worker_profiles')
    op.drop_table('student_profiles')
    op.drop_table('rooms')
    op.drop_table('locations')
    op.drop_table('wings')
    op.drop_table('floors')
    op.drop_table('hostels')
