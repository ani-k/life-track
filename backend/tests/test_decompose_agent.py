"""
Tests for DecomposeAgent and LLMClient provider routing.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.decompose import DecomposeAgent, _assign_positions, _build_messages
from app.schemas.ai import LLMDecomposeOutput, SubNodeProposal


# ─────────────────────────────────────────────────────────────────────────────
# _assign_positions
# ─────────────────────────────────────────────────────────────────────────────


def test_positions_single_node_centered():
    nodes = [SubNodeProposal(title="X")]
    _assign_positions(nodes)
    assert nodes[0].offset_x == 0.0
    assert nodes[0].offset_y == 200.0


def test_positions_two_nodes_symmetric():
    nodes = [SubNodeProposal(title="A"), SubNodeProposal(title="B")]
    _assign_positions(nodes)
    assert nodes[0].offset_x == -140.0
    assert nodes[1].offset_x == 140.0
    assert nodes[0].offset_y == nodes[1].offset_y == 200.0


def test_positions_three_nodes():
    nodes = [SubNodeProposal(title=f"T{i}") for i in range(3)]
    _assign_positions(nodes)
    x_vals = [n.offset_x for n in nodes]
    # All x positions should be distinct
    assert len(set(x_vals)) == 3
    # Middle node should be at x=0
    assert nodes[1].offset_x == 0.0


def test_positions_empty_list():
    nodes: list[SubNodeProposal] = []
    _assign_positions(nodes)  # must not raise
    assert nodes == []


def test_positions_custom_y_offset():
    nodes = [SubNodeProposal(title="X")]
    _assign_positions(nodes, y_offset=300.0)
    assert nodes[0].offset_y == 300.0


# ─────────────────────────────────────────────────────────────────────────────
# _build_messages
# ─────────────────────────────────────────────────────────────────────────────


def test_build_messages_contains_title():
    msgs = _build_messages("Build a rocket", None, 5, None, [])
    user_msg = msgs[-1]["content"]
    assert "Build a rocket" in user_msg


def test_build_messages_contains_max_children():
    msgs = _build_messages("X", None, 7, None, [])
    assert "7" in msgs[-1]["content"]


def test_build_messages_includes_context_hint():
    msgs = _build_messages("X", None, 5, "focus on backend", [])
    assert "focus on backend" in msgs[-1]["content"]


def test_build_messages_includes_existing_nodes():
    from app.schemas.node import NodeLLMView
    existing = [
        NodeLLMView(
            id=uuid.uuid4(), title="Existing node", node_type="task",
            status="pending", priority="medium", tags=[], description=None,
        )
    ]
    msgs = _build_messages("X", None, 5, None, existing)
    assert "Existing node" in msgs[-1]["content"]


def test_build_messages_system_is_first():
    msgs = _build_messages("X", None, 5, None, [])
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"


# ─────────────────────────────────────────────────────────────────────────────
# DecomposeAgent
# ─────────────────────────────────────────────────────────────────────────────


def _make_agent(proposals: list[SubNodeProposal], reasoning: str = "") -> DecomposeAgent:
    mock_llm = MagicMock()
    mock_llm._model = "gpt-4o"
    mock_llm.chat_structured = AsyncMock(
        return_value=LLMDecomposeOutput(sub_nodes=proposals, reasoning=reasoning)
    )
    return DecomposeAgent(mock_llm)


@pytest.mark.asyncio
async def test_decompose_returns_proposals():
    agent = _make_agent([
        SubNodeProposal(title="Write tests", node_type="task"),
        SubNodeProposal(title="Set up CI", node_type="milestone"),
    ])
    result = await agent.decompose(uuid.uuid4(), "Build a web app", None)
    assert len(result.sub_nodes) == 2
    assert result.sub_nodes[0].title == "Write tests"


@pytest.mark.asyncio
async def test_decompose_sets_positions():
    agent = _make_agent([SubNodeProposal(title=f"T{i}") for i in range(3)])
    result = await agent.decompose(uuid.uuid4(), "Goal", None)
    positions = {n.offset_x for n in result.sub_nodes}
    assert len(positions) == 3  # each node has unique x


@pytest.mark.asyncio
async def test_decompose_empty_result():
    agent = _make_agent([], reasoning="Already atomic")
    result = await agent.decompose(uuid.uuid4(), "Atomic task", None)
    assert result.sub_nodes == []
    assert result.reasoning == "Already atomic"


@pytest.mark.asyncio
async def test_decompose_passes_correct_schema():
    """chat_structured must be called with LLMDecomposeOutput as schema."""
    mock_llm = MagicMock()
    mock_llm._model = "gpt-4o"
    mock_llm.chat_structured = AsyncMock(
        return_value=LLMDecomposeOutput(sub_nodes=[])
    )
    agent = DecomposeAgent(mock_llm)
    await agent.decompose(uuid.uuid4(), "Goal", None)
    schema_arg = mock_llm.chat_structured.call_args.args[1]
    assert schema_arg is LLMDecomposeOutput


@pytest.mark.asyncio
async def test_decompose_sets_parent_node_id():
    agent = _make_agent([SubNodeProposal(title="T")])
    pid = uuid.uuid4()
    result = await agent.decompose(pid, "Goal", None)
    assert result.parent_node_id == pid


@pytest.mark.asyncio
async def test_decompose_provider_used_cloud():
    mock_llm = MagicMock()
    mock_llm._model = "gpt-4o"
    mock_llm.chat_structured = AsyncMock(return_value=LLMDecomposeOutput(sub_nodes=[]))
    result = await DecomposeAgent(mock_llm).decompose(uuid.uuid4(), "X", None)
    assert result.provider_used == "cloud"


@pytest.mark.asyncio
async def test_decompose_provider_used_local():
    mock_llm = MagicMock()
    mock_llm._model = "ollama/gemma3:2b"
    mock_llm.chat_structured = AsyncMock(return_value=LLMDecomposeOutput(sub_nodes=[]))
    result = await DecomposeAgent(mock_llm).decompose(uuid.uuid4(), "X", None)
    assert result.provider_used == "local"


# ─────────────────────────────────────────────────────────────────────────────
# LLMClient provider routing
# ─────────────────────────────────────────────────────────────────────────────


def _settings(**kwargs):
    from app.core.config import Settings
    return Settings(secret_key="a-very-long-secret-key-32chars!!", **kwargs)


def test_for_provider_cloud_uses_litellm_model():
    from app.core.llm import LLMClient
    s = _settings(litellm_model="gpt-4o")
    c = LLMClient.for_provider("cloud", s)
    assert c._model == "gpt-4o"


def test_for_provider_local_uses_ollama_prefix():
    from app.core.llm import LLMClient
    s = _settings(ollama_model="gemma3:2b")
    c = LLMClient.for_provider("local", s)
    assert c._model == "ollama/gemma3:2b"


def test_for_provider_local_model_override():
    from app.core.llm import LLMClient
    s = _settings(ollama_model="gemma3:2b")
    c = LLMClient.for_provider("local", s, model="llama3.1")
    assert c._model == "ollama/llama3.1"


def test_for_ollama_custom_url_sets_api_base():
    from app.core.llm import LLMClient
    s = _settings(ollama_base_url="http://my-tunnel:11434")
    c = LLMClient.for_ollama(s)
    assert c._extra.get("api_base") == "http://my-tunnel:11434"


def test_for_ollama_default_url_no_api_base():
    """Default Ollama URL — LiteLLM handles routing, no api_base needed."""
    from app.core.llm import LLMClient
    s = _settings()
    c = LLMClient.for_ollama(s)
    assert "api_base" not in c._extra


def test_json_mode_cloud():
    from app.core.llm import LLMClient
    assert LLMClient(_settings(litellm_model="gpt-4o"))._supports_json_mode() is True


def test_json_mode_ollama_false():
    from app.core.llm import LLMClient
    c = LLMClient.for_provider("local", _settings())
    assert c._supports_json_mode() is False


def test_json_mode_anthropic_false():
    from app.core.llm import LLMClient
    c = LLMClient(_settings(litellm_model="anthropic/claude-3-5-sonnet"))
    assert c._supports_json_mode() is False
