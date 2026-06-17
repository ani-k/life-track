"""
Node REST endpoints — full CRUD.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.node import Node
from app.schemas.node import NodeCreate, NodeUpdate, NodeResponse
from app.crud.node import get_node, list_nodes

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/{node_id}", response_model=NodeResponse)
async def get_node_endpoint(
    node_id: uuid.UUID,
    space_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> NodeResponse:
    """Get a single node by ID (requires space_id query param for authorization)."""
    node = await get_node(db, node_id, space_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found in space {space_id}")
    return NodeResponse.model_validate(node)


@router.patch("/{node_id}", response_model=NodeResponse)
async def update_node_endpoint(
    node_id: uuid.UUID,
    space_id: uuid.UUID,
    update: NodeUpdate,
    db: AsyncSession = Depends(get_db),
) -> NodeResponse:
    """Update a node. Only provided fields are updated (partial update)."""
    node = await get_node(db, node_id, space_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    # Apply updates
    for field, value in update.model_dump(exclude_unset=True).items():
        if field == "status" and value == "completed" and node.status != "completed":
            node.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]
        elif field == "status" and value != "completed":
            node.completed_at = None  # type: ignore[assignment]
        setattr(node, field, value)

    await db.flush()
    await db.refresh(node)
    return NodeResponse.model_validate(node)


@router.delete("/{node_id}", status_code=204)
async def delete_node_endpoint(
    node_id: uuid.UUID,
    space_id: uuid.UUID,
    soft: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete a node.
    - soft=True (default): sets status='archived' (soft delete for undo)
    - soft=False: hard delete from DB
    """
    node = await get_node(db, node_id, space_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")

    if soft:
        node.status = "archived"  # type: ignore[assignment]
        await db.flush()
    else:
        await db.delete(node)
        await db.flush()
    from fastapi import Response
    return Response(status_code=204)
