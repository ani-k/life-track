"""
Tests for Node, Space, and Template CRUD endpoints (Step 5).
Uses mocked database and models.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.nodes import get_node_endpoint, update_node_endpoint, delete_node_endpoint
from app.api.v1.spaces import list_spaces, create_space, get_space, get_space_graph
from app.api.v1.templates import seed_from_template
from app.schemas.node import NodeUpdate
from app.schemas.graph import SpaceCreate


_NOW = datetime(2024, 6, 14, tzinfo=timezone.utc)


def _make_node(node_id: str | None = None, title: str = "Test Node", status: str = "pending"):
    """Create a mock Node object with proper attributes for Pydantic."""
    class MockNode:
        def __init__(self):
            self.id = uuid.uuid4() if node_id is None else (uuid.UUID(node_id) if len(node_id) == 36 else uuid.uuid4())
            self.space_id = uuid.uuid4()
            self.title = title
            self.node_type = "task"
            self.status = status
            self.priority = "medium"
            self.tags = []
            self.description = None
            self.due_date = None
            self.canvas_data = {"position": {"x": 0, "y": 0}, "dimensions": {"width": 220, "height": 80}, "style": {"color": "#84855c", "icon": None}, "collapsed": False}
            self.ai_generated = False
            self.ai_model = None
            self.ai_confidence = None
            self.ai_provenance = {"ai_generated": False, "ai_model": None, "ai_confidence": None, "generated_at": None}
            self.completed_at = None
            self.created_at = _NOW
            self.updated_at = _NOW
    
    return MockNode()


def _make_space(space_id: str | None = None, name: str = "My Space"):
    """Create a mock Space object with proper attributes for Pydantic."""
    class MockSpace:
        def __init__(self):
            self.id = uuid.uuid4() if space_id is None else (uuid.UUID(space_id) if len(space_id) == 36 else uuid.uuid4())
            self.user_id = uuid.uuid4()
            self.name = name
            self.description = None
            self.canvas_settings = {}
            # Use a dict for viewport so Pydantic can validate it
            self.viewport = {"x": 0.0, "y": 0.0, "zoom": 1.0}
            self.created_at = _NOW
            self.updated_at = _NOW
    
    return MockSpace()


# ── Node CRUD Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_node_success():
    node = _make_node()
    db = AsyncMock()
    with patch("app.api.v1.nodes.get_node", AsyncMock(return_value=node)):
        result = await get_node_endpoint(node.id, node.space_id, db)
        assert result.id == node.id
        assert result.title == "Test Node"


@pytest.mark.asyncio
async def test_get_node_not_found():
    db = AsyncMock()
    with patch("app.api.v1.nodes.get_node", AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc_info:
            await get_node_endpoint(uuid.uuid4(), uuid.uuid4(), db)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_node_title():
    node = _make_node(title="Old Title")
    db = AsyncMock()
    update_data = NodeUpdate(title="New Title")
    
    with patch("app.api.v1.nodes.get_node", AsyncMock(return_value=node)):
        result = await update_node_endpoint(node.id, node.space_id, update_data, db)
        assert node.title == "New Title"


@pytest.mark.asyncio
async def test_update_node_status_to_completed_sets_completed_at():
    node = _make_node(status="pending")
    node.completed_at = None
    db = AsyncMock()
    update_data = NodeUpdate(status="completed")
    
    with patch("app.api.v1.nodes.get_node", AsyncMock(return_value=node)):
        await update_node_endpoint(node.id, node.space_id, update_data, db)
        assert node.status == "completed"
        assert node.completed_at is not None


@pytest.mark.asyncio
async def test_update_node_status_to_pending_clears_completed_at():
    node = _make_node(status="completed")
    node.completed_at = _NOW
    db = AsyncMock()
    update_data = NodeUpdate(status="pending")
    
    with patch("app.api.v1.nodes.get_node", AsyncMock(return_value=node)):
        await update_node_endpoint(node.id, node.space_id, update_data, db)
        assert node.status == "pending"
        assert node.completed_at is None


@pytest.mark.asyncio
async def test_delete_node_soft_archives():
    node = _make_node(status="pending")
    db = AsyncMock()
    
    with patch("app.api.v1.nodes.get_node", AsyncMock(return_value=node)):
        await delete_node_endpoint(node.id, node.space_id, soft=True, db=db)
        assert node.status == "archived"
        db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_node_hard_deletes_from_db():
    node = _make_node()
    db = AsyncMock()
    
    with patch("app.api.v1.nodes.get_node", AsyncMock(return_value=node)):
        await delete_node_endpoint(node.id, node.space_id, soft=False, db=db)
        db.delete.assert_called_once_with(node)


# ── Space CRUD Tests ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_spaces_returns_all():
    spaces = [_make_space("s1", "Space 1"), _make_space("s2", "Space 2")]
    db = AsyncMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = spaces
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    db.execute.return_value = mock_result
    
    result = await list_spaces(db=db)
    assert len(result) == 2
    assert result[0].name == "Space 1"


@pytest.mark.asyncio
async def test_create_space():
    db = AsyncMock()
    space_data = SpaceCreate(name="Test Space", description="Test description")
    
    # Mock the database operations
    async def mock_flush():
        # After flush, the space will have an ID assigned by DB
        pass
    
    async def mock_refresh(obj):
        # Simulate setting DB-generated fields
        obj.id = uuid.uuid4()
        obj.created_at = _NOW
        obj.updated_at = _NOW
        # Use a dict for viewport so Pydantic can validate it
        obj.viewport = {"x": 0.0, "y": 0.0, "zoom": 1.0}
        pass
    
    db.flush = mock_flush
    db.refresh = mock_refresh
    
    result = await create_space(space_data, db)
    assert result.name == "Test Space"
    assert result.description == "Test description"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_get_space_success():
    space = _make_space()
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = space
    db.execute.return_value = mock_result
    
    result = await get_space(space.id, db)
    assert result.name == "My Space"


@pytest.mark.asyncio
async def test_get_space_not_found():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    db.execute.return_value = mock_result
    
    with pytest.raises(HTTPException) as exc_info:
        await get_space(uuid.uuid4(), db)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_space_graph_returns_nodes_and_edges():
    space = _make_space()
    nodes = [_make_node("n1", "Node 1"), _make_node("n2", "Node 2")]
    edges = []
    
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = space
    db.execute.return_value = mock_result
    
    with (
        patch("app.api.v1.spaces.list_nodes", AsyncMock(return_value=nodes)),
        patch("app.api.v1.spaces.list_edges", AsyncMock(return_value=edges)),
    ):
        result = await get_space_graph(space.id, db)
        assert len(result.nodes) == 2
        assert result.nodes[0].title == "Node 1"


# ── Template Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_seed_from_template_health():
    db = AsyncMock()
    
    async def mock_flush():
        pass
    
    db.flush = mock_flush
    
    created_space = _make_space(name="Health & Wellness")
    created_nodes = [
        _make_node("n1", "Annual Health Checkup"),
        _make_node("n2", "Gym 3x per week"),
        _make_node("n3", "Meal prep Sundays"),
        _make_node("n4", "Track daily water intake"),
    ]
    
    with (
        patch("app.api.v1.templates.Space", return_value=created_space),
        patch("app.api.v1.templates.Node", side_effect=[MagicMock(id=n.id) for n in created_nodes]),
        patch("app.api.v1.templates.Edge", return_value=MagicMock()),
        patch("app.api.v1.templates.list_nodes", AsyncMock(return_value=created_nodes)),
        patch("app.api.v1.templates.list_edges", AsyncMock(return_value=[])),
    ):
        result = await seed_from_template("health", db=db)
        assert result.space.name == "Health & Wellness"
        assert len(result.nodes) == 4
        assert result.nodes[0].title == "Annual Health Checkup"


@pytest.mark.asyncio
async def test_seed_from_template_invalid_key():
    db = AsyncMock()
    with pytest.raises(HTTPException) as exc_info:
        await seed_from_template("invalid_template", db=db)  # type: ignore
    assert exc_info.value.status_code == 404
