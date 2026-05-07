"""Add token_blacklist table for logout token revocation

Revision ID: 20260507_add_token_blacklist
Revises: 20260505_add_report_tables
Create Date: 2026-05-07 16:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = '20260507_add_token_blacklist'
down_revision = '20260505_add_report_tables'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'token_blacklist',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('token_jti', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('token_sub', sa.String(36), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('blacklisted_at', sa.DateTime(), default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table('token_blacklist')
