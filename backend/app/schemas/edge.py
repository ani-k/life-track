"""
Pydantic v2 schemas for Edge.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


EdgeType = Literal["parent_child", "dependency", "cross_space", "ai_suggested", "reference"]


class EdgeStyle(BaseModel):
    animated: bool = False
    stroke: str = Field(default="#84855c", pattern=r"^#[0-9a-fA-F]{6}$")
    stroke_width: Annotated[float, Field(gt=0, le=20)] = 2.0
    marker_end: str = "arrow"  # Vue Flow marker token


class EdgeBase(BaseModel):
    source_id: uuid.UUID
    target_id: uuid.UUID
    edge_type: EdgeType = "parent_child"
    label: Annotated[str | None, Field(default=None, max_length=200)]
    style: EdgeStyle = Field(default_factory=EdgeStyle)
    # Only relevant when edge_type == "cross_space"
    target_space_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def cross_space_requires_target_space(self) -> "EdgeBase":
        if self.edge_type == "cross_space" and self.target_space_id is None:
            raise ValueError("cross_space edges must include target_space_id")
        if self.source_id == self.target_id:
            raise ValueError("An edge cannot connect a node to itself")
        return self


class EdgeCreate(EdgeBase):
    pass


class EdgeUpdate(BaseModel):
    label: Annotated[str | None, Field(default=None, max_length=200)]
    edge_type: EdgeType | None = None
    style: EdgeStyle | None = None


class EdgeResponse(EdgeBase):
    id: uuid.UUID
    space_id: uuid.UUID
    ai_generated: bool
    created_at: object  # datetime, from_attributes
    updated_at: object

    model_config = {"from_attributes": True}
