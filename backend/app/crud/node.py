"""
Node + Edge CRUD operations.
All functions are async and take an explicit AsyncSession.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.edge import Edge
from app.models.node import Node
from app.schemas.ai import SubNodeProposal
from app.schemas.node import Position


async def get_node(
    db: AsyncSession, node_id: uuid.UUID, space_id: uuid.UUID
) -> Node | None:
    result = await db.execute(
        select(Node).where(Node.id == node_id, Node.space_id == space_id)
    )
    return result.scalar_one_or_none()


async def list_nodes(db: AsyncSession, space_id: uuid.UUID) -> list[Node]:
    result = await db.execute(select(Node).where(Node.space_id == space_id))
    return list(result.scalars().all())


async def list_edges(db: AsyncSession, space_id: uuid.UUID) -> list[Edge]:
    result = await db.execute(select(Edge).where(Edge.space_id == space_id))
    return list(result.scalars().all())


async def create_node_from_proposal(
    db: AsyncSession,
    space_id: uuid.UUID,
    proposal: SubNodeProposal,
    parent_position: Position,
    ai_model: str,
    ai_confidence: float = 0.85,
) -> Node:
    """Persist one accepted AI sub-node proposal."""
    node = Node(
        space_id=space_id,
        node_type=proposal.node_type,
        title=proposal.title,
        description=proposal.description,
        tags=proposal.tags,
        status="pending",
        priority=proposal.priority,
        canvas_data={
            "position": {
                "x": parent_position.x + proposal.offset_x,
                "y": parent_position.y + proposal.offset_y,
            },
            "dimensions": {"width": 220, "height": 80},
            "style": {"color": "#84855c", "icon": None},
            "collapsed": False,
        },
        ai_generated=True,
        ai_model=ai_model,
        ai_confidence=ai_confidence,
    )
    db.add(node)
    await db.flush()
    return node


async def create_node_raw(
    db: AsyncSession,
    space_id: uuid.UUID,
    title: str,
    node_type: str = "task",
    description: str | None = None,
    priority: str = "medium",
    x: float = 200.0,
    y: float = 200.0,
    ai_model: str = "chat-tool",
) -> Node:
    """Create a node directly (from AI chat tool call)."""
    node = Node(
        space_id=space_id,
        node_type=node_type,
        title=title,
        description=description,
        tags=[],
        status="pending",
        priority=priority,
        canvas_data={
            "position": {"x": x, "y": y},
            "dimensions": {"width": 220, "height": 80},
            "style": {"color": "#84855c", "icon": None},
            "collapsed": False,
        },
        ai_generated=True,
        ai_model=ai_model,
        ai_confidence=0.9,
    )
    db.add(node)
    await db.flush()
    return node


async def update_node_status_by_id(
    db: AsyncSession, node_id: uuid.UUID, space_id: uuid.UUID, status: str
) -> Node | None:
    node = await get_node(db, node_id, space_id)
    if node is None:
        return None
    node.status = status  # type: ignore[assignment]
    if status == "completed":
        node.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
    else:
        node.completed_at = None  # type: ignore[assignment]
    await db.flush()
    return node


async def create_edge(
    db: AsyncSession,
    space_id: uuid.UUID,
    source_id: uuid.UUID,
    target_id: uuid.UUID,
    edge_type: str = "parent_child",
    ai_generated: bool = True,
) -> Edge:
    edge = Edge(
        space_id=space_id,
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        style={
            "animated": True,
            "stroke": "#84855c",
            "stroke_width": 2,
            "marker_end": "arrow",
        },
        ai_generated=ai_generated,
    )
    db.add(edge)
    await db.flush()
    return edge
