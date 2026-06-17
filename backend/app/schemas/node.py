"""
Pydantic v2 schemas for Node — request, response, and the canonical
JSON representation consumed by both the Vue Flow canvas and the LLM.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums as Literals for IDE completion + strict validation ──────────────────

NodeType = Literal["goal", "milestone", "task", "note", "ai_suggestion"]
NodeStatus = Literal["pending", "in_progress", "completed", "archived"]
NodePriority = Literal["low", "medium", "high", "critical"]


# ── Canvas sub-schemas ─────────────────────────────────────────────────────────

class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class Dimensions(BaseModel):
    width: Annotated[float, Field(gt=0, le=2000)] = 220.0
    height: Annotated[float, Field(gt=0, le=2000)] = 80.0


class NodeStyle(BaseModel):
    color: str = Field(default="#84855c", pattern=r"^#[0-9a-fA-F]{6}$")
    icon: str | None = Field(default=None, max_length=10)  # emoji or short code


class CanvasData(BaseModel):
    position: Position = Field(default_factory=Position)
    dimensions: Dimensions = Field(default_factory=Dimensions)
    style: NodeStyle = Field(default_factory=NodeStyle)
    collapsed: bool = False


# ── AI provenance ──────────────────────────────────────────────────────────────

class AIProvenance(BaseModel):
    ai_generated: bool = False
    ai_model: str | None = Field(default=None, max_length=100)
    ai_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


# ── Core node schemas ──────────────────────────────────────────────────────────

class NodeBase(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=500)]
    description: Annotated[str | None, Field(default=None, max_length=5000)]
    node_type: NodeType = "task"
    status: NodeStatus = "pending"
    priority: NodePriority = "medium"
    tags: list[Annotated[str, Field(max_length=50)]] = Field(default_factory=list)
    due_date: datetime | None = None

    @field_validator("tags")
    @classmethod
    def tags_max_count(cls, v: list[str]) -> list[str]:
        if len(v) > 20:
            raise ValueError("A node can have at most 20 tags")
        return [t.strip().lower() for t in v]


class NodeCreate(NodeBase):
    canvas_data: CanvasData = Field(default_factory=CanvasData)
    # AI provenance is set server-side; not accepted from client on creation
    # (prevents spoofing ai_generated=True)


class NodeUpdate(BaseModel):
    """All fields optional — PATCH semantics."""
    title: Annotated[str | None, Field(default=None, min_length=1, max_length=500)]
    description: Annotated[str | None, Field(default=None, max_length=5000)]
    node_type: NodeType | None = None
    status: NodeStatus | None = None
    priority: NodePriority | None = None
    tags: list[Annotated[str, Field(max_length=50)]] | None = None
    due_date: datetime | None = None
    canvas_data: CanvasData | None = None

    @field_validator("tags")
    @classmethod
    def tags_max_count(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and len(v) > 20:
            raise ValueError("A node can have at most 20 tags")
        return v


class NodeResponse(NodeBase):
    """Full node representation returned by the API and stored in Vue Flow."""
    id: uuid.UUID
    space_id: uuid.UUID
    canvas_data: CanvasData
    ai_provenance: AIProvenance
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def model_validate(cls, obj: object, **kwargs: object) -> "NodeResponse":
        if hasattr(obj, "__dict__") or hasattr(obj, "__table__"):
            # When mapping from SQLAlchemy ORM, obj doesn't have artificial `ai_provenance` attribute
            raw: dict = {
                "id": obj.id,
                "space_id": obj.space_id,
                "title": obj.title,
                "description": obj.description,
                "node_type": obj.node_type,
                "status": obj.status,
                "priority": obj.priority,
                "tags": obj.tags,
                "due_date": obj.due_date,
                "canvas_data": obj.canvas_data,
                "ai_provenance": {
                    "ai_generated": getattr(obj, "ai_generated", False),
                    "ai_model": getattr(obj, "ai_model", None),
                    "ai_confidence": getattr(obj, "ai_confidence", None),
                },
                "completed_at": obj.completed_at,
                "created_at": obj.created_at,
                "updated_at": obj.updated_at,
            }
            return cls.model_validate(raw, **kwargs)
        return super().model_validate(obj, **kwargs)


# ── LLM-optimised minimal schema (used in AI prompts to reduce token usage) ────

class NodeLLMView(BaseModel):
    """Compact node representation injected into LLM system prompts."""
    id: uuid.UUID
    title: str
    node_type: NodeType
    status: NodeStatus
    priority: NodePriority
    tags: list[str]
    description: str | None

    model_config = {"from_attributes": True}
