"""
Node — the core unit of the goal graph.

Node types:
  goal        — High-level life goal (root of a subtree)
  milestone   — Measurable checkpoint toward a goal
  task        — Concrete, actionable work item
  note        — Free-form annotation (no status tracking)
  ai_suggestion — AI-proposed node awaiting user acceptance

Status lifecycle:
  pending → in_progress → completed
                       ↘ archived (soft-delete from canvas)
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, DateTime, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, GUID, new_uuid

if TYPE_CHECKING:
    from .space import Space
    from .edge import Edge


NODE_TYPES = ("goal", "milestone", "task", "note", "ai_suggestion")
NODE_STATUSES = ("pending", "in_progress", "completed", "archived")
NODE_PRIORITIES = ("low", "medium", "high", "critical")


class Node(Base, TimestampMixin):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=new_uuid
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Core content — stored in JSON for LLM-friendly serialization
    node_type: Mapped[str] = mapped_column(
        SAEnum(*NODE_TYPES, name="node_type_enum"), nullable=False, default="task"
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Status & priority
    status: Mapped[str] = mapped_column(
        SAEnum(*NODE_STATUSES, name="node_status_enum"), nullable=False, default="pending"
    )
    priority: Mapped[str] = mapped_column(
        SAEnum(*NODE_PRIORITIES, name="node_priority_enum"), nullable=False, default="medium"
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Coords mirrored directly for quick indexing / drag update
    x: Mapped[float] = mapped_column(default=0.0, nullable=False)
    y: Mapped[float] = mapped_column(default=0.0, nullable=False)

    # Canvas layout — JSON keeps Vue Flow position/style separate from business data
    canvas_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: {
            "position": {"x": 0, "y": 0},
            "dimensions": {"width": 220, "height": 80},
            "style": {"color": "#84855c", "icon": None},
            "collapsed": False,
        },
    )

    # AI provenance — lets the UI badge AI-generated nodes
    ai_generated: Mapped[bool] = mapped_column(default=False, nullable=False)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(nullable=True)  # 0.0–1.0

    space: Mapped["Space"] = relationship("Space", back_populates="nodes")

    # Edges where this node is the source or target
    outgoing_edges: Mapped[list["Edge"]] = relationship(
        "Edge", foreign_keys="Edge.source_id", back_populates="source_node", cascade="all, delete-orphan", primaryjoin="Node.id == Edge.source_id"
    )
    incoming_edges: Mapped[list["Edge"]] = relationship(
        "Edge", foreign_keys="Edge.target_id", back_populates="target_node", cascade="all, delete-orphan", primaryjoin="Node.id == Edge.target_id"
    )

    def __repr__(self) -> str:
        return f"<Node id={self.id} type={self.node_type} title={self.title!r}>"
