"""
Edge — directed relationship between two nodes.

Edge types:
  parent_child  — Hierarchical decomposition (goal → milestone → task)
  dependency    — Task B cannot start until Task A is done
  cross_space   — Link a node to a node in a DIFFERENT space (target_space_id populated)
  ai_suggested  — AI-proposed connection awaiting user acceptance
  reference     — Soft associative link (no semantic ordering)
"""
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, ForeignKey, Enum as SAEnum, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .space import Space
    from .node import Node


EDGE_TYPES = ("parent_child", "dependency", "cross_space", "ai_suggested", "reference")


class Edge(Base, TimestampMixin):
    __tablename__ = "edges"
    __table_args__ = (
        # Prevent self-loops at the DB level
        CheckConstraint("source_id != target_id", name="ck_edge_no_self_loop"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # For cross_space edges, store the foreign space reference
    target_space_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="SET NULL"), nullable=True
    )

    edge_type: Mapped[str] = mapped_column(
        SAEnum(*EDGE_TYPES, name="edge_type_enum"), nullable=False, default="parent_child"
    )
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Vue Flow visual style (animated, stroke color, marker type)
    style: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    ai_generated: Mapped[bool] = mapped_column(default=False, nullable=False)

    space: Mapped["Space"] = relationship("Space", foreign_keys=[space_id], back_populates="edges")
    source_node: Mapped["Node"] = relationship("Node", foreign_keys=[source_id], back_populates="outgoing_edges")
    target_node: Mapped["Node"] = relationship("Node", foreign_keys=[target_id], back_populates="incoming_edges")

    def __repr__(self) -> str:
        return f"<Edge {self.source_id} --[{self.edge_type}]--> {self.target_id}>"
