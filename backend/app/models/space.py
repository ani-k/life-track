"""
Space = a named canvas/workspace containing a goal graph.
Each user can have multiple spaces (e.g. "Career", "Health", "2025 Goals").

auth_status: MVP — no authentication yet.
  user_id is stored for future use but carries no FK constraint until
  the auth layer (users table + JWT) is wired in (see TODO: auth).
  The column is nullable so spaces can be created without a user record.
"""
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, GUID, new_uuid

if TYPE_CHECKING:
    from .node import Node
    from .edge import Edge


class Space(Base, TimestampMixin):
    __tablename__ = "spaces"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=new_uuid
    )
    # TODO(auth): once User model and JWT are active, restore:
    #   user_id: Mapped[uuid.UUID] = mapped_column(
    #       GUID, ForeignKey("users.id", ondelete="CASCADE"),
    #       nullable=False, index=True
    #   )
    # For MVP: stored for tracking, no FK enforced, nullable.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Persists the viewport state (pan + zoom) for canvas restoration
    viewport: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=lambda: {"x": 0, "y": 0, "zoom": 1.0}
    )

    nodes: Mapped[list["Node"]] = relationship(
        "Node", back_populates="space", cascade="all, delete-orphan"
    )
    edges: Mapped[list["Edge"]] = relationship(
        "Edge",
        foreign_keys="[Edge.space_id]",
        back_populates="space",
        cascade="all, delete-orphan",
        primaryjoin="Space.id == Edge.space_id"
    )

    def __repr__(self) -> str:
        return f"<Space id={self.id} name={self.name}>"
