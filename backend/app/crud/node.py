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
    result = await db.execute(
        select(Node).where(Node.space_id == space_id, Node.status != "archived")
    )
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
        x=float(parent_position.x + proposal.offset_x),
        y=float(parent_position.y + proposal.offset_y),
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
    """Create a node directly (from AI chat tool call) with auto-shifting layout to avoid stacking/overlapping."""
    # To prevent node stacking, dynamically scan if this position is busy, and shift.
    fixed_x = float(x)
    fixed_y = float(y)
    
    # Simple collision shifting: check if a node already exists near this point
    existing_result = await db.execute(
        select(Node).where(Node.space_id == space_id, Node.status != "archived")
    )
    existing_nodes = existing_result.scalars().all()
    
    collision = True
    passes = 0
    while collision and passes < 40:
        collision = False
        for old_node in existing_nodes:
            # If distance is less than width (220px) and height (80px), shift horizontally
            dx = abs(old_node.x - fixed_x)
            dy = abs(old_node.y - fixed_y)
            if dx < 240 and dy < 120:
                fixed_x += 260.0 # shift to the right
                if fixed_x > 1800: # wrap around the imaginary row
                    fixed_x = 100.0 + (passes * 30)
                    fixed_y += 140.0
                collision = True
                break
        passes += 1

    node = Node(
        space_id=space_id,
        node_type=node_type,
        title=title,
        description=description,
        tags=[],
        status="pending",
        priority=priority,
        x=fixed_x,
        y=fixed_y,
        canvas_data={
            "position": {"x": fixed_x, "y": fixed_y},
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
    ai_generated: bool = False, # Сплошные стрелки при создании связей по умолчанию!
) -> Edge:
    edge = Edge(
        space_id=space_id,
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        style={
            "animated": False, # Убираем анимацию пунктира, делаем сплошными!
            "stroke": "#84855c",
            "stroke_width": 2,
            "marker_end": "arrow",
        },
        ai_generated=ai_generated,
    )
    db.add(edge)
    await db.flush()
    return edge
