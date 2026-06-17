"""
Alembic initial migration — creates all tables for the Life Goal Canvas.
Run: alembic upgrade head
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enum types ──────────────────────────────────────────────────────────────
    node_type_enum = postgresql.ENUM(
        "goal", "milestone", "task", "note", "ai_suggestion",
        name="node_type_enum", create_type=True
    )
    node_status_enum = postgresql.ENUM(
        "pending", "in_progress", "completed", "archived",
        name="node_status_enum", create_type=True
    )
    node_priority_enum = postgresql.ENUM(
        "low", "medium", "high", "critical",
        name="node_priority_enum", create_type=True
    )
    edge_type_enum = postgresql.ENUM(
        "parent_child", "dependency", "cross_space", "ai_suggested", "reference",
        name="edge_type_enum", create_type=True
    )

    for enum in (node_type_enum, node_status_enum, node_priority_enum, edge_type_enum):
        enum.create(op.get_bind(), checkfirst=True)

    # ── users ───────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── spaces ──────────────────────────────────────────────────────────────────
    op.create_table(
        "spaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("viewport", postgresql.JSONB, nullable=False, server_default='{"x":0,"y":0,"zoom":1.0}'),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_spaces_user_id", "spaces", ["user_id"])

    # ── nodes ───────────────────────────────────────────────────────────────────
    op.create_table(
        "nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("node_type", sa.Enum(name="node_type_enum", create_type=False), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.String(5000), nullable=True),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("status", sa.Enum(name="node_status_enum", create_type=False), nullable=False),
        sa.Column("priority", sa.Enum(name="node_priority_enum", create_type=False), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canvas_data", postgresql.JSONB, nullable=False),
        sa.Column("ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_model", sa.String(100), nullable=True),
        sa.Column("ai_confidence", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_nodes_space_id", "nodes", ["space_id"])

    # ── edges ───────────────────────────────────────────────────────────────────
    op.create_table(
        "edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True),
        sa.Column("edge_type", sa.Enum(name="edge_type_enum", create_type=False), nullable=False),
        sa.Column("label", sa.String(200), nullable=True),
        sa.Column("style", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("source_id != target_id", name="ck_edge_no_self_loop"),
    )
    op.create_index("ix_edges_space_id", "edges", ["space_id"])
    op.create_index("ix_edges_source_id", "edges", ["source_id"])
    op.create_index("ix_edges_target_id", "edges", ["target_id"])

    # ── ai_sessions ─────────────────────────────────────────────────────────────
    op.create_table(
        "ai_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("space_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("messages", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("model_params", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_sessions_space_id", "ai_sessions", ["space_id"])


def downgrade() -> None:
    op.drop_table("ai_sessions")
    op.drop_table("edges")
    op.drop_table("nodes")
    op.drop_table("spaces")
    op.drop_table("users")
    for name in ("node_type_enum", "node_status_enum", "node_priority_enum", "edge_type_enum"):
        op.execute(f"DROP TYPE IF EXISTS {name}")
