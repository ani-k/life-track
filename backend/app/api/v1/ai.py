"""
AI endpoints: Decompose, Accept, Chat.
"""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat import ChatOrchestrator, clear_session
from app.agents.decompose import DecomposeAgent
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.llm import LLMClient
from app.crud.node import (
    create_edge,
    create_node_from_proposal,
    get_node,
    list_nodes,
)
from app.schemas.ai import (
    AIChatRequest,
    AIChatResponse,
    DecomposeAcceptRequest,
    DecomposeAcceptResponse,
    DecompositionRequest,
    DecompositionResponse,
)
from app.schemas.node import NodeLLMView, NodeResponse
from app.schemas.edge import EdgeResponse
from app.schemas.problem import AIProblemDetail

log = logging.getLogger(__name__)
router = APIRouter(prefix="/spaces/{space_id}/ai", tags=["ai"])


# ── POST /decompose ───────────────────────────────────────────────────────────


@router.post("/decompose", response_model=DecompositionResponse)
async def decompose_node(
    space_id: uuid.UUID,
    req: DecompositionRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DecompositionResponse:
    parent_node = await get_node(db, req.node_id, space_id)
    if parent_node is None:
        raise HTTPException(status_code=404, detail=f"Node {req.node_id} not found")

    all_nodes = await list_nodes(db, space_id)
    existing = [
        NodeLLMView.model_validate(n)
        for n in all_nodes
        if str(n.id) != str(req.node_id)
    ]

    llm = LLMClient.for_provider(req.provider, settings, model=req.local_model)
    agent = DecomposeAgent(llm)
    try:
        result = await agent.decompose(
            parent_node_id=parent_node.id,
            title=parent_node.title,
            description=parent_node.description,
            max_children=req.max_children,
            context_hint=req.context_hint,
            existing_nodes=existing,
        )
        return result
    except json.JSONDecodeError as exc:
        raise AIProblemDetail(
            status_code=502,
            detail=f"LLM returned invalid JSON: {exc}",
            instance=f"/spaces/{space_id}/ai/decompose",
            extra={"provider": req.provider, "model_used": getattr(llm, "_model", "")},
        )
    except Exception as exc:
        log.exception("Decompose failed: %s", exc)
        raise AIProblemDetail(
            status_code=502,
            detail=f"LLM request failed: {exc}",
            instance=f"/spaces/{space_id}/ai/decompose",
        )


# ── POST /decompose/accept ────────────────────────────────────────────────────


@router.post("/decompose/accept", response_model=DecomposeAcceptResponse)
async def accept_decomposition(
    space_id: uuid.UUID,
    req: DecomposeAcceptRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> DecomposeAcceptResponse:
    if not req.accepted_nodes:
        raise HTTPException(status_code=422, detail="accepted_nodes must not be empty")

    parent_node = await get_node(db, req.parent_node_id, space_id)
    if parent_node is None:
        raise HTTPException(status_code=404, detail=f"Parent node {req.parent_node_id} not found")

    created_nodes, created_edges = [], []
    for proposal in req.accepted_nodes:
        node = await create_node_from_proposal(
            db, space_id, proposal, req.parent_position, settings.litellm_model
        )
        edge = await create_edge(db, space_id, parent_node.id, node.id, req.suggested_edge_type)
        created_nodes.append(node)
        created_edges.append(edge)

    return DecomposeAcceptResponse(
        created_nodes=[NodeResponse.model_validate(n) for n in created_nodes],
        created_edges=[EdgeResponse.model_validate(e) for e in created_edges],
    )


# ── POST /chat ────────────────────────────────────────────────────────────────


@router.post("/chat", response_model=AIChatResponse)
async def chat(
    space_id: uuid.UUID,
    req: AIChatRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AIChatResponse:
    """
    AI chat with tool use. The LLM can see and modify the canvas.

    - Cloud (OpenAI): native function calling → tool results → final reply (2 LLM calls when tools used)
    - Local (Ollama): single structured-output call returning reply + tool_calls together
    """
    llm = LLMClient.for_provider(req.provider, settings, model=req.local_model)
    orchestrator = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
    try:
        return await orchestrator.run(
            user_message=req.message,
            session_id=req.session_id,
        )
    except json.JSONDecodeError as exc:
        raise AIProblemDetail(
            status_code=502,
            detail=f"LLM returned invalid JSON in chat: {exc}",
            instance=f"/spaces/{space_id}/ai/chat",
            extra={"provider": req.provider},
        )
    except Exception as exc:
        log.exception("Chat orchestrator failed: %s", exc)
        raise AIProblemDetail(
            status_code=502,
            detail=f"LLM request failed: {exc}",
            instance=f"/spaces/{space_id}/ai/chat",
        )


# ── DELETE /chat/sessions/{session_id} ────────────────────────────────────────


@router.delete("/chat/sessions/{session_id}", status_code=204, response_model=None)
async def delete_chat_session(space_id: uuid.UUID, session_id: uuid.UUID) -> None:
    """Clear conversation history for a session."""
    clear_session(session_id)
