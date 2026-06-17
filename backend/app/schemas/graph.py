"""
Graph schema — the complete serialised canvas state.
This is the canonical JSON format exchanged with the frontend
and fed to the LLM for context.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from .node import NodeResponse, NodeLLMView
from .edge import EdgeResponse


class Viewport(BaseModel):
    x: float = 0.0
    y: float = 0.0
    zoom: float = Field(default=1.0, gt=0.0, le=10.0)


# ── Space / Graph schemas ──────────────────────────────────────────────────────

class SpaceBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class SpaceCreate(SpaceBase):
    viewport: Viewport = Field(default_factory=Viewport)


class SpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    viewport: Viewport | None = None


class SpaceResponse(SpaceBase):
    id: uuid.UUID
    # TODO(auth): make non-optional once auth is wired in
    user_id: uuid.UUID | None = None
    viewport: Viewport
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: object, **kwargs: object) -> "SpaceResponse":
        # SQLAlchemy stores viewport as a plain dict (JSONB).
        # Pydantic can't auto-coerce it from ORM attributes, so we convert
        # to a plain dict first, keeping ORM object untouched.
        if hasattr(obj, "__dict__") or hasattr(obj, "__table__"):
            raw: dict = {
                "id": obj.id,
                "user_id": obj.user_id,
                "name": obj.name,
                "description": obj.description,
                "viewport": obj.viewport if isinstance(obj.viewport, dict) else obj.viewport,
                "created_at": obj.created_at,
                "updated_at": obj.updated_at,
            }
            return cls.model_validate(raw, **kwargs)
        return super().model_validate(obj, **kwargs)


class GraphResponse(BaseModel):
    """
    Full graph payload — used on canvas load and as AI context.
    Mirrors Vue Flow's expected { nodes, edges } structure.
    """
    space: SpaceResponse
    nodes: list[NodeResponse]
    edges: list[EdgeResponse]


class GraphLLMContext(BaseModel):
    """
    Compact graph snapshot injected into LLM prompts.
    Omits canvas layout data to reduce token count.
    """
    space_id: uuid.UUID
    space_name: str
    nodes: list[NodeLLMView]
    # Edges as simple source → target pairs
    edges: list[dict]  # [{"id": ..., "source": ..., "target": ..., "type": ...}]

    @classmethod
    def from_graph(cls, graph: GraphResponse) -> "GraphLLMContext":
        return cls(
            space_id=graph.space.id,
            space_name=graph.space.name,
            nodes=[NodeLLMView.model_validate(n) for n in graph.nodes],
            edges=[
                {
                    "id": str(e.id),
                    "source": str(e.source_id),
                    "target": str(e.target_id),
                    "type": e.edge_type,
                }
                for e in graph.edges
            ],
        )
