"""
Tests for the ChatOrchestrator (Step 4 — AI Chat with Tool Use).
Uses unittest.mock to avoid real LLM/DB calls.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.chat import (
    ChatOrchestrator,
    _SESSIONS,
    _build_system_prompt,
    _get_or_create_session,
    clear_session,
)
from app.core.llm import LLMClient, LLMResponse
from app.schemas.ai import AIChatResponse, OrchestratorOutput, ToolCallSpec
from app.schemas.node import NodeResponse
from app.schemas.edge import EdgeResponse


# ── Helpers ───────────────────────────────────────────────────────────────────

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _make_node(title: str = "Test Goal"):
    """Build a minimal mock that satisfies NodeResponse.model_validate()."""
    n = MagicMock()
    n.id = uuid.uuid4()
    n.title = title
    n.node_type = "goal"
    n.status = "pending"
    n.priority = "medium"
    n.space_id = uuid.uuid4()
    n.description = None
    n.tags = []
    n.due_date = None
    n.canvas_data = {"position": {"x": 0, "y": 0}}
    n.ai_generated = True
    n.ai_model = "gpt-4o"
    n.ai_confidence = 0.9
    n.ai_provenance = {
        "model": "gpt-4o",
        "confidence": 0.9,
        "prompt_version": "v1",
        "generated_at": _NOW.isoformat(),
    }
    n.created_at = _NOW
    n.updated_at = _NOW
    n.completed_at = None
    return n


def _make_edge(space_id: uuid.UUID | None = None):
    """Build a minimal mock that satisfies EdgeResponse.model_validate()."""
    e = MagicMock()
    e.id = uuid.uuid4()
    e.source_id = uuid.uuid4()
    e.target_id = uuid.uuid4()
    e.edge_type = "parent_child"
    e.space_id = space_id or uuid.uuid4()
    e.label = None
    e.target_space_id = None
    e.style = {}
    e.ai_generated = True
    e.created_at = _NOW
    e.updated_at = _NOW
    return e


def _make_llm(supports_tools: bool = True) -> LLMClient:
    llm = MagicMock()
    llm._model = "gpt-4o" if supports_tools else "ollama/gemma"
    llm._supports_tool_calling.return_value = supports_tools
    return llm


# ── System prompt ─────────────────────────────────────────────────────────────


def test_system_prompt_includes_nodes():
    node = _make_node("Learn Rust")
    edge = _make_edge()
    prompt = _build_system_prompt([node], [edge], use_tools=False)
    assert "Learn Rust" in prompt
    assert str(node.id) in prompt


def test_system_prompt_tools_description_for_non_native():
    prompt = _build_system_prompt([], [], use_tools=False)
    assert "add_node" in prompt
    assert "connect_nodes" in prompt
    assert "update_node_status" in prompt


def test_system_prompt_no_tools_description_when_native():
    prompt = _build_system_prompt([], [], use_tools=True)
    # When using native tools, description block is omitted from system prompt
    assert "canvas tools" not in prompt


def test_system_prompt_caps_large_graphs():
    nodes = [_make_node(f"Node {i}") for i in range(60)]
    prompt = _build_system_prompt(nodes, [], use_tools=False)
    # prompt should mention total count
    assert "60 total" in prompt


# ── Session management ────────────────────────────────────────────────────────


def test_create_new_session():
    _SESSIONS.clear()
    session = _get_or_create_session(None)
    assert session.id is not None
    assert session.messages == []


def test_reuse_existing_session():
    _SESSIONS.clear()
    sid = uuid.uuid4()
    s1 = _get_or_create_session(sid)
    s1.messages.append({"role": "user", "content": "hello"})
    s2 = _get_or_create_session(sid)
    assert s1 is s2
    assert len(s2.messages) == 1


def test_clear_session():
    _SESSIONS.clear()
    sid = uuid.uuid4()
    _get_or_create_session(sid)
    assert str(sid) in _SESSIONS
    clear_session(sid)
    assert str(sid) not in _SESSIONS


def test_clear_nonexistent_session_is_noop():
    clear_session(uuid.uuid4())  # should not raise


# ── ChatOrchestrator (mocked LLM + DB) ───────────────────────────────────────


@pytest.fixture(autouse=True)
def clean_sessions():
    _SESSIONS.clear()
    yield
    _SESSIONS.clear()


@pytest.mark.asyncio
async def test_chat_openai_no_tools():
    """When LLM returns no tool calls, reply is passed through directly."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()

    llm = _make_llm(supports_tools=True)
    llm.chat_with_tools = AsyncMock(return_value=("Great plan!", [], [], 42))

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run("What should I focus on?")

    assert isinstance(result, AIChatResponse)
    assert result.reply == "Great plan!"
    assert result.mutations == []
    assert result.tokens_used == 42


@pytest.mark.asyncio
async def test_chat_openai_add_node_tool():
    """add_node tool should create a node and add GraphMutationAction."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()

    llm = _make_llm(supports_tools=True)
    new_node = _make_node("Buy guitar")
    new_node.space_id = space_id

    tool_call = {
        "name": "add_node",
        "arguments": {"title": "Buy guitar", "node_type": "task"},
        "call_id": "call_abc",
    }
    raw_tool_call = MagicMock()
    raw_tool_call.function.name = "add_node"

    llm.chat_with_tools = AsyncMock(return_value=("", [tool_call], [raw_tool_call], 10))
    llm.chat = AsyncMock(return_value=LLMResponse("Done! Created Buy guitar node.", 8, "gpt-4o"))

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
        patch("app.agents.chat.create_node_raw", AsyncMock(return_value=new_node)),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run("Add a task to buy a guitar")

    assert result.reply == "Done! Created Buy guitar node."
    assert len(result.mutations) == 1
    assert result.mutations[0].action == "add_node"
    assert result.tokens_used == 18  # 10 + 8


@pytest.mark.asyncio
async def test_chat_openai_update_status_tool():
    """update_node_status tool should produce an update_node mutation."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()
    node_id = uuid.uuid4()

    llm = _make_llm(supports_tools=True)
    updated_node = _make_node("Learn Spanish")
    updated_node.id = node_id
    updated_node.status = "completed"
    updated_node.completed_at = None

    tool_call = {
        "name": "update_node_status",
        "arguments": {"node_id": str(node_id), "status": "completed"},
        "call_id": "call_xyz",
    }
    raw_tc = MagicMock()
    llm.chat_with_tools = AsyncMock(return_value=("", [tool_call], [raw_tc], 5))
    llm.chat = AsyncMock(return_value=LLMResponse("Marked as completed!", 4, "gpt-4o"))

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
        patch("app.agents.chat.update_node_status_by_id", AsyncMock(return_value=updated_node)),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run(f"Mark {node_id} as done")

    assert result.reply == "Marked as completed!"
    assert len(result.mutations) == 1
    assert result.mutations[0].action == "update_node"


@pytest.mark.asyncio
async def test_chat_openai_connect_nodes_tool():
    """connect_nodes tool should produce an add_edge mutation."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()
    src_id = uuid.uuid4()
    tgt_id = uuid.uuid4()

    llm = _make_llm(supports_tools=True)
    edge = _make_edge(space_id=space_id)
    edge.source_id = src_id
    edge.target_id = tgt_id

    tool_call = {
        "name": "connect_nodes",
        "arguments": {"source_id": str(src_id), "target_id": str(tgt_id)},
        "call_id": "call_conn",
    }
    raw_tc = MagicMock()
    llm.chat_with_tools = AsyncMock(return_value=("", [tool_call], [raw_tc], 6))
    llm.chat = AsyncMock(return_value=LLMResponse("Connected!", 3, "gpt-4o"))

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
        patch("app.agents.chat.create_edge", AsyncMock(return_value=edge)),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run("Connect those two nodes")

    assert result.reply == "Connected!"
    assert len(result.mutations) == 1
    assert result.mutations[0].action == "add_edge"


@pytest.mark.asyncio
async def test_chat_connect_nodes_self_loop_returns_error():
    """Connecting a node to itself should not produce a mutation."""
    _SESSIONS.clear()
    space_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    db = AsyncMock()
    same_id = uuid.uuid4()

    llm = _make_llm(supports_tools=True)
    tool_call = {
        "name": "connect_nodes",
        "arguments": {"source_id": str(same_id), "target_id": str(same_id)},
        "call_id": "call_loop",
    }
    raw_tc = MagicMock()
    llm.chat_with_tools = AsyncMock(return_value=("", [tool_call], [raw_tc], 5))
    llm.chat = AsyncMock(return_value=LLMResponse("Sorry, cannot self-loop.", 3, "gpt-4o"))

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run("Connect a node to itself")

    assert result.mutations == []


@pytest.mark.asyncio
async def test_chat_ollama_fallback_no_tools():
    """Ollama path uses chat_structured; empty tool_calls = no mutations."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()

    llm = _make_llm(supports_tools=False)
    output = OrchestratorOutput(reply="Hello from Gemma!", tool_calls=[])
    llm.chat_structured = AsyncMock(return_value=output)

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run("Hello")

    assert result.reply == "Hello from Gemma!"
    assert result.mutations == []


@pytest.mark.asyncio
async def test_chat_ollama_fallback_with_add_node():
    """Ollama path: tool call in structured output should create node."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()

    llm = _make_llm(supports_tools=False)
    new_node = _make_node("Run a marathon")
    new_node.space_id = space_id

    tc = ToolCallSpec(name="add_node", arguments={"title": "Run a marathon", "node_type": "goal"})
    output = OrchestratorOutput(reply="Added marathon goal!", tool_calls=[tc])
    llm.chat_structured = AsyncMock(return_value=output)

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
        patch("app.agents.chat.create_node_raw", AsyncMock(return_value=new_node)),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run("Add a marathon goal")

    assert result.reply == "Added marathon goal!"
    assert len(result.mutations) == 1
    assert result.mutations[0].action == "add_node"


@pytest.mark.asyncio
async def test_chat_session_persists_history():
    """Messages should accumulate across multiple calls with same session_id."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()
    session_id = uuid.uuid4()

    llm = _make_llm(supports_tools=True)
    llm.chat_with_tools = AsyncMock(return_value=("Response 1", [], [], 5))

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        r1 = await orch.run("Message 1", session_id=session_id)
        assert r1.session_id == session_id
        assert len(_SESSIONS[str(session_id)].messages) == 2  # user + assistant

        llm.chat_with_tools = AsyncMock(return_value=("Response 2", [], [], 5))
        r2 = await orch.run("Message 2", session_id=session_id)
        assert r2.session_id == session_id
        assert len(_SESSIONS[str(session_id)].messages) == 4  # 2 turns


@pytest.mark.asyncio
async def test_chat_graph_context_injected():
    """System prompt must contain node titles from the loaded graph."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()

    llm = _make_llm(supports_tools=True)
    captured_messages: list = []

    async def capture_tools(messages, tools):
        captured_messages.extend(messages)
        return ("ok", [], [], 1)

    llm.chat_with_tools = capture_tools

    node = _make_node("Write a novel")
    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[node])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        await orch.run("What should I do next?")

    system_msg = captured_messages[0]
    assert system_msg["role"] == "system"
    assert "Write a novel" in system_msg["content"]


@pytest.mark.asyncio
async def test_chat_empty_graph():
    """Orchestrator should work fine with an empty graph (no nodes/edges)."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()

    llm = _make_llm(supports_tools=True)
    llm.chat_with_tools = AsyncMock(return_value=("You have no goals yet!", [], [], 5))

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run("Help me start")

    assert result.reply == "You have no goals yet!"


@pytest.mark.asyncio
async def test_chat_update_nonexistent_node():
    """update_node_status on missing node should not add mutation."""
    _SESSIONS.clear()
    space_id = uuid.uuid4()
    db = AsyncMock()
    node_id = uuid.uuid4()

    llm = _make_llm(supports_tools=True)
    tool_call = {
        "name": "update_node_status",
        "arguments": {"node_id": str(node_id), "status": "completed"},
        "call_id": "call_miss",
    }
    raw_tc = MagicMock()
    llm.chat_with_tools = AsyncMock(return_value=("", [tool_call], [raw_tc], 3))
    llm.chat = AsyncMock(return_value=LLMResponse("Node not found.", 2, "gpt-4o"))

    with (
        patch("app.agents.chat.list_nodes", AsyncMock(return_value=[])),
        patch("app.agents.chat.list_edges", AsyncMock(return_value=[])),
        patch("app.agents.chat.update_node_status_by_id", AsyncMock(return_value=None)),
    ):
        orch = ChatOrchestrator(llm=llm, space_id=space_id, db=db)
        result = await orch.run("Mark that node done")

    assert result.mutations == []
