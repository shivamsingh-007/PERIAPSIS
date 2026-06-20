"""initial schema with auth tokens, secrets, agents

Revision ID: 001_initial
Revises: 
Create Date: 2026-06-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- auth_tokens ---
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("token_data", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_revoked", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # --- secret_records ---
    op.create_table(
        "secret_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("encrypted_value", sa.Text, nullable=False),
        sa.Column("value_hash", sa.String(64), nullable=False),
        sa.Column("environment", sa.String(50), nullable=False, server_default="dev"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("tags", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", "environment", name="uq_secret_records_tenant_name_env"),
    )

    # --- agents ---
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(255), nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("api_key_hash", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("permissions", postgresql.JSONB, nullable=True),
        sa.Column("allowed_tools", postgresql.JSONB, nullable=True),
        sa.Column("denied_tools", postgresql.JSONB, nullable=True),
        sa.Column("trust_score", sa.Numeric(3, 2), nullable=False, server_default=sa.text("1.0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_agents_tenant_name"),
    )


def downgrade() -> None:
    op.drop_table("agents")
    op.drop_table("secret_records")
    op.drop_table("auth_tokens")
