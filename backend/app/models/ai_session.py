"""
AISession — persists the chat history per space so the LLM has context
across multiple user interactions (decompose, refine, cross-link suggestions).
"""
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, GUID, new_uuid

if TYPE_CHECKING:
    from .space import Space


class AISession(Base, TimestampMixin):
    __tablename__ = "ai_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=new_uuid
    )
    space_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # OpenAI-compatible message history: [{"role": "user"|"assistant"|"system", "content": "..."}]
    messages: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Which model was used and its parameters
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="gpt-4o")
    model_params: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Total tokens consumed (for usage monitoring / billing guards)
    total_tokens: Mapped[int] = mapped_column(default=0, nullable=False)

    space: Mapped["Space"] = relationship("Space", primaryjoin="Space.id == AISession.space_id")

    def __repr__(self) -> str:
        return f"<AISession id={self.id} space={self.space_id} msgs={len(self.messages)}>"
