"""add missing columns to users and notifications

Revision ID: a1b2c3d4e5f6
Revises: 49c1415f308b
Create Date: 2026-09-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '49c1415f308b'
branch_labels = None
depends_on = None


def upgrade():
    # إضافة عمود dark_mode إلى جدول users
    op.add_column('users', sa.Column('dark_mode', sa.Boolean(), nullable=True, server_default=sa.false()))
    # إضافة عمودي read_at و expires_at إلى جدول notifications
    op.add_column('notifications', sa.Column('read_at', sa.DateTime(), nullable=True))
    op.add_column('notifications', sa.Column('expires_at', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('notifications', 'expires_at')
    op.drop_column('notifications', 'read_at')
    op.drop_column('users', 'dark_mode')
