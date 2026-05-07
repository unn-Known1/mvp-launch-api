"""Add report tables for automated reporting engine

Revision ID: 20260505_add_report_tables
Revises: 20260505_initial_schema
Create Date: 2026-05-05 18:50:00.000000

"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260505_add_report_tables"
down_revision = "20260505_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    # Create report_templates table
    op.create_table(
        "report_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now(), nullable=True),
    )
    op.create_index("ix_report_templates_user_id", "report_templates", ["user_id"])

    # Create scheduled_reports table
    op.create_table(
        "scheduled_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column(
            "template_id",
            UUID(as_uuid=True),
            sa.ForeignKey("report_templates.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("time_of_day", sa.String(8), nullable=False, server_default="08:00"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        sa.Column("recipients", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), onupdate=sa.func.now(), nullable=True),
    )
    op.create_index("ix_scheduled_reports_user_id", "scheduled_reports", ["user_id"])
    op.create_index(
        "ix_scheduled_reports_next_run_at", "scheduled_reports", ["next_run_at"]
    )
    op.create_index(
        "ix_scheduled_reports_is_active", "scheduled_reports", ["is_active"]
    )

    # Create report_deliveries table
    op.create_table(
        "report_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "scheduled_report_id",
            UUID(as_uuid=True),
            sa.ForeignKey("scheduled_reports.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("pdf_url", sa.String(512), nullable=True),
        sa.Column("csv_urls", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_report_deliveries_scheduled_report_id",
        "report_deliveries",
        ["scheduled_report_id"],
    )
    op.create_index("ix_report_deliveries_status", "report_deliveries", ["status"])
    op.create_index(
        "ix_report_deliveries_created_at", "report_deliveries", ["created_at"]
    )


def downgrade():
    op.drop_table("report_deliveries")
    op.drop_table("scheduled_reports")
    op.drop_table("report_templates")
