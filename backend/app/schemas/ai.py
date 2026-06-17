"""
AI-specific Pydantic schemas — decompose, chat, and tool calling.
"""
from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from .node import NodeResponse, NodeType, NodePriority, Position
from .edge import EdgeResponse, EdgeType

Provider = Literal["cloud", "local"]


# ── Decomposition ─────────────────────────────────────────────────────────────

class SubNodeProposal(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=500)]
    description: str | None = Field(default=None, max_length=2000)
    node_type: NodeType = "task"
    priority: NodePriority = "medium"
    tags: list[str] = Field(default_factory=list)
    offset_x: float = 0.0
    offset_y: float = 200.0


class DecompositionRequest(BaseModel):
    node_id: uuid.UUID
    depth: Annotated[int, Field(ge=1, le=3)] = 1
    max_children: Annotated[int, Field(ge=1, le=10)] = 5
    context_hint: str | None = Field(default=None, max_length=500)
    provider: Provider = "cloud"
    local_model: str | None = Field(default=None, max_length=100)


class DecompositionResponse(BaseModel):
    parent_node_id: uuid.UUID
    sub_nodes: list[SubNodeProposal]
    suggested_edge_type: EdgeType = "parent_child"
    reasoning: str = Field(default="", max_length=1000)
    provider_used: str = "cloud"
    model_used: str = ""


class LLMDecomposeOutput(BaseModel):
    sub_nodes: list[SubNodeProposal]
    reasoning: str = Field(default="", max_length=1000)


class DecomposeAcceptRequest(BaseModel):
    parent_node_id: uuid.UUID
    accepted_nodes: list[SubNodeProposal]
    parent_position: Position = Field(default_factory=Position)
    suggested_edge_type: EdgeType = "parent_child"


class DecomposeAcceptResponse(BaseModel):
    created_nodes: list[NodeResponse]
    created_edges: list[EdgeResponse]


# ── Tool calling schemas ───────────────────────────────────────────────────────

class ToolCallSpec(BaseModel):
    """A single tool call as returned by a non-OpenAI provider (Ollama fallback)."""
    name: Literal["add_node", "connect_nodes", "update_node_status", "mass_create_nodes", "reorganize_graph"]
    arguments: dict


class OrchestratorOutput(BaseModel):
    """
    Structured output schema for Ollama/non-OpenAI providers.
    Combines the text reply and tool calls in one JSON object.
    Both reply and tool_calls are returned in a single inference call.
    """
    reply: str = Field(description="Your text response to the user (required, non-empty)")
    tool_calls: list[ToolCallSpec] = Field(
        default_factory=list,
        description="List of canvas tools to execute. Leave empty if no changes needed.",
    )


# ── Graph mutation (returned to frontend) ────────────────────────────────────

class GraphMutationAction(BaseModel):
    action: Literal["add_node", "update_node", "add_edge", "delete_node", "delete_edge"]
    payload: dict


# ── Chat request / response ───────────────────────────────────────────────────

class AIChatRequest(BaseModel):
    message: Annotated[str, Field(min_length=1, max_length=4000)]
    session_id: uuid.UUID | None = None
    provider: Provider = "cloud"
    local_model: str | None = Field(default=None, max_length=100)


class AIChatResponse(BaseModel):
    session_id: uuid.UUID
    reply: str
    mutations: list[GraphMutationAction] = Field(default_factory=list)
    tokens_used: int
