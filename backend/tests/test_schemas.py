"""
Schema validation tests — Step 1 Architecture phase.
Tests cover: valid creation, boundary violations, cross-space edge rules,
self-loop prevention, AI confidence bounds, and LLM context serialisation.
"""
import uuid
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.node import NodeCreate, NodeUpdate, NodeLLMView, CanvasData, NodeStyle
from app.schemas.edge import EdgeCreate, EdgeUpdate
from app.schemas.graph import (
    SpaceCreate, SpaceUpdate, Viewport, GraphResponse, GraphLLMContext, SpaceResponse
)
from app.schemas.ai import (
    DecompositionRequest, DecompositionResponse, SubNodeProposal,
    AIChatRequest, AIChatResponse, GraphMutationAction,
)


# ─────────────────────────────────────────────────────────────────────────────
# NodeCreate
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeCreate:
    def test_minimal_valid(self):
        n = NodeCreate(title="Learn Rust")
        assert n.title == "Learn Rust"
        assert n.node_type == "task"
        assert n.status == "pending"
        assert n.priority == "medium"
        assert n.tags == []

    def test_all_node_types_accepted(self):
        for nt in ("goal", "milestone", "task", "note", "ai_suggestion"):
            n = NodeCreate(title="X", node_type=nt)
            assert n.node_type == nt

    def test_invalid_node_type_rejected(self):
        with pytest.raises(ValidationError):
            NodeCreate(title="X", node_type="epic")  # not in Literal

    def test_title_empty_rejected(self):
        with pytest.raises(ValidationError):
            NodeCreate(title="")

    def test_title_too_long_rejected(self):
        with pytest.raises(ValidationError):
            NodeCreate(title="a" * 501)

    def test_description_max_length(self):
        NodeCreate(title="X", description="d" * 5000)
        with pytest.raises(ValidationError):
            NodeCreate(title="X", description="d" * 5001)

    def test_tags_normalised_to_lowercase(self):
        n = NodeCreate(title="X", tags=["Fitness", "HEALTH"])
        assert n.tags == ["fitness", "health"]

    def test_tags_stripped(self):
        n = NodeCreate(title="X", tags=["  rust  "])
        assert n.tags == ["rust"]

    def test_tags_max_count(self):
        with pytest.raises(ValidationError):
            NodeCreate(title="X", tags=[f"tag{i}" for i in range(21)])

    def test_canvas_data_default_position(self):
        n = NodeCreate(title="X")
        assert n.canvas_data.position.x == 0.0
        assert n.canvas_data.position.y == 0.0

    def test_canvas_style_invalid_color(self):
        with pytest.raises(ValidationError):
            NodeCreate(title="X", canvas_data=CanvasData(style=NodeStyle(color="not-a-hex")))

    def test_canvas_dimensions_zero_rejected(self):
        from app.schemas.node import Dimensions
        with pytest.raises(ValidationError):
            Dimensions(width=0, height=100)

    def test_valid_priority_values(self):
        for p in ("low", "medium", "high", "critical"):
            n = NodeCreate(title="X", priority=p)
            assert n.priority == p


# ─────────────────────────────────────────────────────────────────────────────
# NodeUpdate (PATCH semantics)
# ─────────────────────────────────────────────────────────────────────────────

class TestNodeUpdate:
    def test_all_none_is_valid(self):
        """A PATCH with no fields should be accepted (no-op update)."""
        u = NodeUpdate()
        assert u.title is None

    def test_partial_update(self):
        u = NodeUpdate(status="completed", priority="high")
        assert u.status == "completed"
        assert u.title is None


# ─────────────────────────────────────────────────────────────────────────────
# EdgeCreate
# ─────────────────────────────────────────────────────────────────────────────

class TestEdgeCreate:
    def _ids(self):
        return uuid.uuid4(), uuid.uuid4()

    def test_valid_edge(self):
        s, t = self._ids()
        e = EdgeCreate(source_id=s, target_id=t)
        assert e.edge_type == "parent_child"

    def test_self_loop_rejected(self):
        node_id = uuid.uuid4()
        with pytest.raises(ValidationError, match="cannot connect a node to itself"):
            EdgeCreate(source_id=node_id, target_id=node_id)

    def test_cross_space_requires_target_space_id(self):
        s, t = self._ids()
        with pytest.raises(ValidationError, match="target_space_id"):
            EdgeCreate(source_id=s, target_id=t, edge_type="cross_space")

    def test_cross_space_valid(self):
        s, t = self._ids()
        e = EdgeCreate(source_id=s, target_id=t, edge_type="cross_space", target_space_id=uuid.uuid4())
        assert e.edge_type == "cross_space"

    def test_all_edge_types_accepted(self):
        s, t = self._ids()
        for et in ("parent_child", "dependency", "ai_suggested", "reference"):
            EdgeCreate(source_id=s, target_id=t, edge_type=et)

    def test_label_max_length(self):
        s, t = self._ids()
        EdgeCreate(source_id=s, target_id=t, label="x" * 200)
        with pytest.raises(ValidationError):
            EdgeCreate(source_id=s, target_id=t, label="x" * 201)


# ─────────────────────────────────────────────────────────────────────────────
# SpaceCreate / Viewport
# ─────────────────────────────────────────────────────────────────────────────

class TestSpaceCreate:
    def test_valid_space(self):
        s = SpaceCreate(name="Career Goals")
        assert s.viewport.zoom == 1.0

    def test_name_too_long_rejected(self):
        with pytest.raises(ValidationError):
            SpaceCreate(name="x" * 201)

    def test_viewport_zoom_bounds(self):
        with pytest.raises(ValidationError):
            Viewport(zoom=0.0)
        with pytest.raises(ValidationError):
            Viewport(zoom=10.1)
        Viewport(zoom=0.01)
        Viewport(zoom=10.0)


# ─────────────────────────────────────────────────────────────────────────────
# AI schemas
# ─────────────────────────────────────────────────────────────────────────────

class TestDecompositionRequest:
    def test_valid_request(self):
        r = DecompositionRequest(node_id=uuid.uuid4())
        assert r.depth == 1
        assert r.max_children == 5

    def test_depth_bounds(self):
        with pytest.raises(ValidationError):
            DecompositionRequest(node_id=uuid.uuid4(), depth=0)
        with pytest.raises(ValidationError):
            DecompositionRequest(node_id=uuid.uuid4(), depth=4)

    def test_max_children_bounds(self):
        with pytest.raises(ValidationError):
            DecompositionRequest(node_id=uuid.uuid4(), max_children=0)
        with pytest.raises(ValidationError):
            DecompositionRequest(node_id=uuid.uuid4(), max_children=11)

    def test_context_hint_max_length(self):
        r = DecompositionRequest(node_id=uuid.uuid4(), context_hint="x" * 500)
        with pytest.raises(ValidationError):
            DecompositionRequest(node_id=uuid.uuid4(), context_hint="x" * 501)


class TestAIChatRequest:
    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            AIChatRequest(message="")

    def test_message_too_long_rejected(self):
        with pytest.raises(ValidationError):
            AIChatRequest(message="x" * 4001)


# ─────────────────────────────────────────────────────────────────────────────
# GraphLLMContext serialisation
# ─────────────────────────────────────────────────────────────────────────────

class TestGraphLLMContext:
    def _make_graph(self) -> GraphResponse:
        now = datetime.now(timezone.utc)
        space = SpaceResponse(
            id=uuid.uuid4(), user_id=uuid.uuid4(),
            name="Test Space", viewport=Viewport(),
            created_at=now, updated_at=now
        )
        return GraphResponse(space=space, nodes=[], edges=[])

    def test_from_empty_graph(self):
        g = self._make_graph()
        ctx = GraphLLMContext.from_graph(g)
        assert ctx.nodes == []
        assert ctx.edges == []
        assert ctx.space_name == "Test Space"
