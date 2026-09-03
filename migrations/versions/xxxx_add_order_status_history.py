"""add order status history

Revision ID: 20240101000000
Revises: 49c1415f308b
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20240101000000'
down_revision = '49c1415f308b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'order_status_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('from_status', sa.String(20), nullable=True),
        sa.Column('to_status', sa.String(20), nullable=False),
        sa.Column('changed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('note', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_order_status_history_order_id', 'order_status_history', ['order_id'])
    op.create_index('ix_order_status_history_changed_by', 'order_status_history', ['changed_by'])


def downgrade():
    op.drop_index('ix_order_status_history_changed_by', table_name='order_status_history')
    op.drop_index('ix_order_status_history_order_id', table_name='order_status_history')
    op.drop_table('order_status_history')
