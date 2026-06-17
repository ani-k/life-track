"""
Template seeding endpoint — create spaces from predefined templates.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.space import Space
from app.models.node import Node
from app.models.edge import Edge
from app.schemas.graph import SpaceResponse, GraphResponse
from app.schemas.node import NodeResponse
from app.schemas.edge import EdgeResponse
from app.crud.node import list_nodes, list_edges

router = APIRouter(prefix="/templates", tags=["templates"])

TEMPLATES_PATH = Path(__file__).parent.parent.parent / "templates" / "space_templates.json"

TemplateKey = Literal["health", "career", "personal"]


def load_templates() -> dict:
    """Load templates from JSON file."""
    with open(TEMPLATES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("")
async def list_templates() -> dict[str, dict]:
    """List available space templates."""
    templates = load_templates()
    # Return only metadata (no nodes/edges details)
    return {
        key: {"name": val["name"], "description": val["description"]}
        for key, val in templates.items()
    }


@router.post("/seed/{template_key}", response_model=GraphResponse, status_code=201)
async def seed_from_template(
    template_key: TemplateKey,
    user_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
) -> GraphResponse:
    """
    Create a new space from a template.
    Instantiates all nodes and edges defined in the template.
    """
    templates = load_templates()
    if template_key not in templates:
        raise HTTPException(status_code=404, detail=f"Template {template_key} not found")

    template = templates[template_key]
    
    # Create space
    space = Space(
        user_id=user_id,
        name=template["name"],
        description=template["description"],
        viewport={"x": 0, "y": 0, "zoom": 1.0},
    )
    db.add(space)
    await db.flush()
    await db.refresh(space)

    # Create nodes
    node_map: dict[int, uuid.UUID] = {}  # template index → DB node ID
    for i, node_def in enumerate(template["nodes"]):
        pos = node_def["position"]
        node = Node(
            space_id=space.id,
            node_type=node_def["node_type"],
            title=node_def["title"],
            description=node_def.get("description"),
            tags=node_def.get("tags", []),
            status="pending",
            priority=node_def.get("priority", "medium"),
            canvas_data={
                "position": {"x": pos["x"], "y": pos["y"]},
                "dimensions": {"width": 220, "height": 80},
                "style": {"color": "#84855c", "icon": None},
                "collapsed": False,
            },
            ai_generated=False,
        )
        db.add(node)
        await db.flush()
        node_map[i] = node.id

    # Create edges
    for edge_def in template.get("edges", []):
        source_id = node_map[edge_def["source"]]
        target_id = node_map[edge_def["target"]]
        edge = Edge(
            space_id=space.id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_def.get("edge_type", "parent_child"),
            style={
                "animated": False,
                "stroke": "#84855c",
                "stroke_width": 2,
                "marker_end": "arrow",
            },
            ai_generated=False,
        )
        db.add(edge)

    await db.flush()

    # Return full graph
    nodes = await list_nodes(db, space.id)
    edges = await list_edges(db, space.id)

    return GraphResponse(
        space=SpaceResponse.model_validate(space),
        nodes=[NodeResponse.model_validate(n) for n in nodes],
        edges=[EdgeResponse.model_validate(e) for e in edges],
    )
