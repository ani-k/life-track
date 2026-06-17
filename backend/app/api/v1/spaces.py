"""
Space REST endpoints — list, create, get full graph.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.space import Space
from app.models.node import Node
from app.schemas.graph import SpaceCreate, SpaceResponse, GraphResponse, SpaceUpdate
from app.schemas.node import NodeCreate, NodeUpdate, NodeResponse, Position
from app.crud.node import list_nodes, list_edges
from app.schemas.edge import EdgeResponse

router = APIRouter(prefix="/spaces", tags=["spaces"])


@router.get("", response_model=list[SpaceResponse])
async def list_spaces(
    user_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[SpaceResponse]:
    """
    List all spaces.
    (In production, filter by authenticated user_id. For MVP, returns all.)
    """
    query = select(Space)
    if user_id:
        query = query.where(Space.user_id == user_id)
    result = await db.execute(query)
    spaces = result.scalars().all()
    return [SpaceResponse.model_validate(s) for s in spaces]


@router.post("", response_model=SpaceResponse, status_code=201)
async def create_space(
    space_data: SpaceCreate,
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """Create a new space.

    TODO(auth): accept authenticated user_id from JWT token instead of None.
    """
    space = Space(
        user_id=None,   # TODO(auth): replace with current_user.id from JWT
        name=space_data.name,
        description=space_data.description,
        viewport={"x": space_data.viewport.x, "y": space_data.viewport.y, "zoom": space_data.viewport.zoom},
    )
    db.add(space)
    await db.flush()
    await db.refresh(space)
    return SpaceResponse.model_validate(space)


@router.get("/{space_id}", response_model=SpaceResponse)
async def get_space(
    space_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """Get a space by ID."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")
    return SpaceResponse.model_validate(space)


@router.patch("/{space_id}", response_model=SpaceResponse)
async def update_space(
    space_id: uuid.UUID,
    payload: SpaceUpdate,
    db: AsyncSession = Depends(get_db),
) -> SpaceResponse:
    """Update a space (rename/description/viewport)."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    if payload.name is not None:
        space.name = payload.name
    if payload.description is not None:
        space.description = payload.description
    if payload.viewport is not None:
        space.viewport = {"x": payload.viewport.x, "y": payload.viewport.y, "zoom": payload.viewport.zoom}

    await db.flush()
    await db.refresh(space)
    return SpaceResponse.model_validate(space)


@router.delete("/{space_id}", status_code=204)
async def delete_space(
    space_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a space and all its associated nodes and edges."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    await db.delete(space)
    await db.flush()
    from fastapi import Response
    return Response(status_code=204)


@router.get("/{space_id}/graph", response_model=GraphResponse)
async def get_space_graph(
    space_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> GraphResponse:
    """Get the full graph (nodes + edges) for a space."""
    # Verify space exists
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    nodes = await list_nodes(db, space_id)
    edges = await list_edges(db, space_id)

    return GraphResponse(
        space=SpaceResponse.model_validate(space),
        nodes=[NodeResponse.model_validate(n) for n in nodes],
        edges=[EdgeResponse.model_validate(e) for e in edges],
    )


@router.post("/{space_id}/nodes", response_model=NodeResponse, status_code=201)
async def create_node_in_space(
    space_id: uuid.UUID,
    payload: NodeCreate,
    db: AsyncSession = Depends(get_db),
) -> NodeResponse:
    """Create a new node in the given space."""
    result = await db.execute(select(Space).where(Space.id == space_id))
    space = result.scalar_one_or_none()
    if space is None:
        raise HTTPException(status_code=404, detail=f"Space {space_id} not found")

    canvas_dict = payload.canvas_data.model_dump() if payload.canvas_data else {}
    pos = canvas_dict.get("position", {"x": 200.0, "y": 200.0})

    node = Node(
        space_id=space_id,
        title=payload.title,
        description=payload.description,
        node_type=payload.node_type,
        status=payload.status,
        priority=payload.priority,
        tags=payload.tags,
        due_date=payload.due_date,
        x=float(pos.get("x", 200.0)),
        y=float(pos.get("y", 200.0)),
        canvas_data=payload.canvas_data.model_dump() if payload.canvas_data else {
            "position": {"x": 200.0, "y": 200.0},
            "dimensions": {"width": 220.0, "height": 80.0},
            "style": {"color": "#84855c", "icon": None},
            "collapsed": False,
        },
    )
    db.add(node)
    await db.flush()
    await db.refresh(node)
    return NodeResponse.model_validate(node)


@router.patch("/{space_id}/nodes/{node_id}/position", response_model=NodeResponse)
async def update_node_position(
    space_id: uuid.UUID,
    node_id: uuid.UUID,
    position: Position,
    db: AsyncSession = Depends(get_db),
) -> NodeResponse:
    """Update a node's canvas position."""
    result = await db.execute(
        select(Node).where(Node.id == node_id, Node.space_id == space_id)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found in space {space_id}")

    # Save directly to mirrored x, y
    node.x = float(position.x)
    node.y = float(position.y)

    canvas = dict(node.canvas_data)
    canvas["position"] = {"x": position.x, "y": position.y}
    node.canvas_data = canvas  # type: ignore[assignment]
    await db.flush()
    await db.refresh(node)
    return NodeResponse.model_validate(node)


@router.patch("/{space_id}/nodes/{node_id}/status", response_model=NodeResponse)
async def update_node_status(
    space_id: uuid.UUID,
    node_id: uuid.UUID,
    body: NodeUpdate,
    db: AsyncSession = Depends(get_db),
) -> NodeResponse:
    """Update a node's status (e.g. pending → completed)."""
    result = await db.execute(
        select(Node).where(Node.id == node_id, Node.space_id == space_id)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found in space {space_id}")

    if body.status is not None:
        node.status = body.status  # type: ignore[assignment]
        if body.status == "completed":
            node.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        else:
            node.completed_at = None  # type: ignore[assignment]

    await db.flush()
    await db.refresh(node)
    return NodeResponse.model_validate(node)
