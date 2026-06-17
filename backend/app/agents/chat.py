"""
ChatOrchestrator — the canvas-aware AI chat agent.

Architecture
============
1. Builds a system prompt injecting the current graph state as a compact JSON summary.
2. Routes to either native tool calling (OpenAI) or structured-output fallback (Ollama/others).
3. Executes tool calls server-side (add_node / connect_nodes / update_node_status).
4. For OpenAI: does a follow-up call with tool results to get the final reply.
5. Returns AIChatResponse with the text reply + GraphMutationAction list.

Session management
==================
Messages are stored in an in-memory dict keyed by session UUID.
(Swap the _SESSIONS dict for an SQLAlchemy AISession query in production.)
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import LLMClient
from app.crud.node import (
    create_edge,
    create_node_raw,
    list_edges,
    list_nodes,
    update_node_status_by_id,
)
from app.schemas.ai import (
    AIChatResponse,
    GraphMutationAction,
    OrchestratorOutput,
    ToolCallSpec,
)
from app.schemas.edge import EdgeResponse
from app.schemas.node import NodeResponse

log = logging.getLogger(__name__)


# ── Tool definitions (OpenAI function-calling format) ─────────────────────────

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "add_node",
            "description": (
                "Add a new goal, milestone, or task node to the goal canvas. "
                "Use this when the user asks to add, create, or plan something new."
            ),
            "parameters": {
                "type": "object",
                "required": ["title", "node_type"],
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The node title (concise, action-oriented)",
                    },
                    "node_type": {
                        "type": "string",
                        "enum": ["goal", "milestone", "task", "note"],
                    },
                    "description": {"type": "string"},
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                        "default": "medium",
                    },
                    "x": {
                        "type": "number",
                        "description": "Canvas X position (default: auto-placed)",
                    },
                    "y": {
                        "type": "number",
                        "description": "Canvas Y position (default: auto-placed)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "connect_nodes",
            "description": (
                "Create a directed edge connecting two existing nodes. "
                "source_id is the parent/dependency; target_id is the child."
            ),
            "parameters": {
                "type": "object",
                "required": ["source_id", "target_id"],
                "properties": {
                    "source_id": {
                        "type": "string",
                        "description": "UUID of the source (parent) node",
                    },
                    "target_id": {
                        "type": "string",
                        "description": "UUID of the target (child) node",
                    },
                    "edge_type": {
                        "type": "string",
                        "enum": ["parent_child", "dependency", "reference"],
                        "default": "parent_child",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_node_status",
            "description": (
                "Change the status of an existing node. "
                "Use node IDs exactly as they appear in the graph context."
            ),
            "parameters": {
                "type": "object",
                "required": ["node_id", "status"],
                "properties": {
                    "node_id": {"type": "string", "description": "UUID of the node to update"},
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "completed", "archived"],
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mass_create_nodes",
            "description": (
                "Create multiple nodes at once with optional connections between them. "
                "Use this when the user asks to add a group of related tasks, "
                "a project plan, or a set of goals in one go."
            ),
            "parameters": {
                "type": "object",
                "required": ["nodes"],
                "properties": {
                    "nodes": {
                        "type": "array",
                        "description": "List of nodes to create",
                        "items": {
                            "type": "object",
                            "required": ["title", "node_type"],
                            "properties": {
                                "title": {"type": "string"},
                                "node_type": {
                                    "type": "string",
                                    "enum": ["goal", "milestone", "task", "note"],
                                },
                                "description": {"type": "string"},
                                "priority": {
                                    "type": "string",
                                    "enum": ["low", "medium", "high", "critical"],
                                    "default": "medium",
                                },
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Tags for this node",
                                },
                            },
                        },
                    },
                    "connections": {
                        "type": "array",
                        "description": "Optional edges between the newly created nodes. Use indices from the nodes array (0-based).",
                        "items": {
                            "type": "object",
                            "required": ["source_index", "target_index"],
                            "properties": {
                                "source_index": {
                                    "type": "integer",
                                    "description": "Index in the nodes array for the source/parent",
                                },
                                "target_index": {
                                    "type": "integer",
                                    "description": "Index in the nodes array for the target/child",
                                },
                                "edge_type": {
                                    "type": "string",
                                    "enum": ["parent_child", "dependency", "reference"],
                                    "default": "parent_child",
                                },
                            },
                        },
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reorganize_graph",
            "description": (
                "Analyze the current graph and suggest structural improvements: "
                "new connections between existing nodes, missing parent-child relationships, "
                "or nodes that should be linked. Does NOT create anything — returns suggestions "
                "as a structured list for the user to review."
            ),
            "parameters": {
                "type": "object",
                "required": ["suggestions"],
                "properties": {
                    "suggestions": {
                        "type": "array",
                        "description": "List of suggested graph changes",
                        "items": {
                            "type": "object",
                            "required": ["type", "reason"],
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["connect", "restructure"],
                                    "description": "Type of suggestion: 'connect' to link two nodes, 'restructure' to propose a new hierarchy",
                                },
                                "source_id": {
                                    "type": "string",
                                    "description": "UUID of the source/parent node (for 'connect' type)",
                                },
                                "target_id": {
                                    "type": "string",
                                    "description": "UUID of the target/child node (for 'connect' type)",
                                },
                                "reason": {
                                    "type": "string",
                                    "description": "Explain why this connection or restructure would improve the graph",
                                },
                                "edge_type": {
                                    "type": "string",
                                    "enum": ["parent_child", "dependency", "reference"],
                                    "default": "parent_child",
                                },
                            },
                        },
                    },
                },
            },
        },
    },
]

TOOLS_DESCRIPTION = """
You have access to the following canvas tools. Use them when appropriate:

• add_node(title, node_type, description?, priority?, x?, y?)
  — Create a new node (goal / milestone / task / note) on the canvas.

• connect_nodes(source_id, target_id, edge_type?)
  — Draw an edge from source_id → target_id. Use exact node UUIDs from the graph.

• update_node_status(node_id, status)
  — Set a node's status to: pending | in_progress | completed | archived.

• mass_create_nodes(nodes, connections?)
  — Create multiple nodes at once with optional edges between them.
    nodes: array of {title, node_type, description?, priority?, tags?}
    connections: array of {source_index, target_index, edge_type?} using 0-based indices.

• reorganize_graph(suggestions)
  — Analyze the graph and return structural suggestions (connect / restructure).
    Does NOT modify the graph — returns suggestions for user review.

Return tool_calls as an array; leave it empty [] if no canvas changes are needed.
Always respond in the `reply` field even when using tools.
"""


# ── System prompt builder ─────────────────────────────────────────────────────


def _build_system_prompt(nodes: list, edges: list, use_tools: bool) -> str:
    nodes_ctx = "\n".join(
        _format_node(n)
        for n in nodes
    )
    edges_ctx = "\n".join(
        f'  {{source: "{e.source_id}", target: "{e.target_id}", type: "{e.edge_type}"}}'
        for e in edges
    )

    graph_block = (
        f"Nodes ({len(nodes)} total):\n[\n{nodes_ctx}\n]\n\n"
        f"Edges ({len(edges)} total):\n[\n{edges_ctx}\n]"
    )

    tools_block = TOOLS_DESCRIPTION if not use_tools else ""

    return (
        "You are an AI assistant embedded in LifeTrack — a visual life-planning canvas.\n"
        "You can see the user's goal graph and modify it using tools.\n\n"
        f"Current graph state:\n{graph_block}\n\n"
        "Guidelines:\n"
        "• Refer to existing nodes by their exact UUID when connecting or updating.\n"
        "• Keep replies concise — the user sees the canvas, not just the chat.\n"
        "• After making changes, briefly list what you created/updated.\n"
        "• When the user asks to analyze or improve their goals, use reorganize_graph to suggest improvements.\n"
        "• For bulk task creation (e.g. 'add steps for X'), use mass_create_nodes.\n"
        f"{tools_block}"
    )


def _format_node(n: object) -> str:
    """Format a node as a compact JSON-like string with key fields."""
    parts = [
        f'id: "{n.id}"',
        f'title: "{n.title}"',
        f'type: "{n.node_type}"',
        f'status: "{n.status}"',
        f'priority: "{n.priority}"',
    ]
    if getattr(n, "description", None):
        desc = n.description[:80].replace('"', "'")
        parts.append(f'description: "{desc}"')
    if getattr(n, "tags", None):
        parts.append(f'tags: {n.tags}')
    if getattr(n, "due_date", None):
        parts.append(f'due_date: "{n.due_date.isoformat()}"')
    return "  {" + ", ".join(parts) + "}"


# ── In-memory session store (replace with DB AISession in production) ─────────


@dataclass
class _Session:
    id: uuid.UUID
    messages: list[dict] = field(default_factory=list)
    total_tokens: int = 0


_SESSIONS: dict[str, _Session] = {}


def _get_or_create_session(session_id: uuid.UUID | None) -> _Session:
    key = str(session_id) if session_id else None
    if key and key in _SESSIONS:
        return _SESSIONS[key]
    s = _Session(id=session_id or uuid.uuid4())
    _SESSIONS[str(s.id)] = s
    return s


def clear_session(session_id: uuid.UUID) -> None:
    _SESSIONS.pop(str(session_id), None)


# ── Orchestrator ──────────────────────────────────────────────────────────────


class ChatOrchestrator:
    """
    Stateless per-request orchestrator.
    Inject a pre-configured LLMClient (cloud or local) from the API layer.
    """

    def __init__(self, llm: LLMClient, space_id: uuid.UUID, db: AsyncSession) -> None:
        self._llm = llm
        self._space_id = space_id
        self._db = db

    async def run(
        self,
        user_message: str,
        session_id: uuid.UUID | None = None,
    ) -> AIChatResponse:
        # 1. Load graph context
        nodes = await list_nodes(self._db, self._space_id)
        edges = await list_edges(self._db, self._space_id)

        # 2. Get or create session
        session = _get_or_create_session(session_id)

        # 3. Build messages
        use_native_tools = self._llm._supports_tool_calling()
        system_msg = _build_system_prompt(nodes, edges, use_native_tools)

        messages: list[dict] = (
            [{"role": "system", "content": system_msg}]
            + session.messages
            + [{"role": "user", "content": user_message}]
        )

        # 4. Call LLM
        mutations: list[GraphMutationAction] = []
        tokens_used = 0

        if use_native_tools:
            reply, mutations, tokens_used = await self._native_tool_loop(messages)
        else:
            reply, mutations, tokens_used = await self._structured_tool_loop(messages)

        # 5. Persist conversation turn
        session.messages.append({"role": "user", "content": user_message})
        session.messages.append({"role": "assistant", "content": reply})
        session.total_tokens += tokens_used

        return AIChatResponse(
            session_id=session.id,
            reply=reply,
            mutations=mutations,
            tokens_used=tokens_used,
        )

    # ── Native tool calling (OpenAI) ──────────────────────────────────

    async def _native_tool_loop(
        self, messages: list[dict]
    ) -> tuple[str, list[GraphMutationAction], int]:
        text, tool_calls, raw_calls, tokens = await self._llm.chat_with_tools(
            messages, TOOLS
        )
        mutations: list[GraphMutationAction] = []

        if not tool_calls:
            return text, mutations, tokens

        # Execute tools
        tool_results: list[dict] = []
        for tc in tool_calls:
            result_str = await self._execute_tool(tc["name"], tc["arguments"], mutations)
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc["call_id"],
                "content": result_str,
            })

        # Follow-up call to get final reply incorporating tool results
        follow_up = list(messages)
        follow_up.append({
            "role": "assistant",
            "content": text or None,
            "tool_calls": raw_calls,
        })
        follow_up.extend(tool_results)

        follow_resp = await self._llm.chat(follow_up)
        tokens += follow_resp.tokens_used
        return follow_resp.content, mutations, tokens

    # ── Structured output fallback (Ollama / other providers) ─────────

    async def _structured_tool_loop(
        self, messages: list[dict]
    ) -> tuple[str, list[GraphMutationAction], int]:
        """
        For Ollama/others: chat_structured returns OrchestratorOutput with
        both the reply text and any tool calls encoded as JSON.
        The schema is injected into the user message automatically by chat_structured.
        """
        output: OrchestratorOutput = await self._llm.chat_structured(
            messages, OrchestratorOutput
        )
        mutations: list[GraphMutationAction] = []
        for tc in output.tool_calls:
            await self._execute_tool(tc.name, tc.arguments, mutations)

        return output.reply, mutations, 0  # Ollama doesn't always report usage

    # ── Tool executor ─────────────────────────────────────────────────

    async def _execute_tool(
        self,
        name: str,
        args: dict,
        mutations: list[GraphMutationAction],
    ) -> str:
        """Execute one tool call and append mutation(s) to the list. Returns JSON result."""
        try:
            if name == "add_node":
                node = await create_node_raw(
                    self._db,
                    space_id=self._space_id,
                    title=args["title"],
                    node_type=args.get("node_type", "task"),
                    description=args.get("description"),
                    priority=args.get("priority", "medium"),
                    x=float(args.get("x", 200 + len(mutations) * 300)),
                    y=float(args.get("y", 300)),
                    ai_model=self._llm._model,
                )
                mutations.append(GraphMutationAction(
                    action="add_node",
                    payload=NodeResponse.model_validate(node).model_dump(mode="json"),
                ))
                return json.dumps({"status": "ok", "node_id": str(node.id)})

            elif name == "connect_nodes":
                source_id = uuid.UUID(args["source_id"])
                target_id = uuid.UUID(args["target_id"])
                if source_id == target_id:
                    return json.dumps({"error": "cannot connect node to itself"})
                edge = await create_edge(
                    self._db,
                    space_id=self._space_id,
                    source_id=source_id,
                    target_id=target_id,
                    edge_type=args.get("edge_type", "parent_child"),
                )
                mutations.append(GraphMutationAction(
                    action="add_edge",
                    payload=EdgeResponse.model_validate(edge).model_dump(mode="json"),
                ))
                return json.dumps({"status": "ok", "edge_id": str(edge.id)})

            elif name == "update_node_status":
                node_id = uuid.UUID(args["node_id"])
                node = await update_node_status_by_id(
                    self._db, node_id, self._space_id, args["status"]
                )
                if node is None:
                    return json.dumps({"error": f"node {node_id} not found"})
                mutations.append(GraphMutationAction(
                    action="update_node",
                    payload={
                        "id": str(node.id),
                        "status": node.status,
                        "completed_at": (
                            node.completed_at.isoformat() if node.completed_at else None
                        ),
                    },
                ))
                return json.dumps({"status": "ok", "node_id": str(node.id), "new_status": node.status})

            elif name == "mass_create_nodes":
                return await self._execute_mass_create(args, mutations)

            elif name == "reorganize_graph":
                return await self._execute_reorganize(args, mutations)

            else:
                return json.dumps({"error": f"Unknown tool: {name}"})

        except Exception as exc:
            log.exception("Tool execution failed: %s(%s) → %s", name, args, exc)
            return json.dumps({"error": str(exc)})

    async def _execute_mass_create(
        self,
        args: dict,
        mutations: list[GraphMutationAction],
    ) -> str:
        """Execute mass_create_nodes: create multiple nodes and optional connections."""
        nodes_data = args.get("nodes", [])
        connections = args.get("connections", [])
        created_ids: list[str] = []

        for nd in nodes_data:
            node = await create_node_raw(
                self._db,
                space_id=self._space_id,
                title=nd["title"],
                node_type=nd.get("node_type", "task"),
                description=nd.get("description"),
                priority=nd.get("priority", "medium"),
                x=float(nd.get("x", 200 + len(created_ids) * 50)),
                y=float(nd.get("y", 200 + len(created_ids) * 120)),
                ai_model=self._llm._model,
            )
            created_ids.append(str(node.id))
            mutations.append(GraphMutationAction(
                action="add_node",
                payload=NodeResponse.model_validate(node).model_dump(mode="json"),
            ))

        # Create connections between newly created nodes
        for conn in connections:
            src_idx = conn["source_index"]
            tgt_idx = conn["target_index"]
            if src_idx >= len(created_ids) or tgt_idx >= len(created_ids):
                continue
            edge = await create_edge(
                self._db,
                space_id=self._space_id,
                source_id=uuid.UUID(created_ids[src_idx]),
                target_id=uuid.UUID(created_ids[tgt_idx]),
                edge_type=conn.get("edge_type", "parent_child"),
            )
            mutations.append(GraphMutationAction(
                action="add_edge",
                payload=EdgeResponse.model_validate(edge).model_dump(mode="json"),
            ))

        return json.dumps({
            "status": "ok",
            "created_count": len(created_ids),
            "connection_count": len(connections),
            "node_ids": created_ids,
        })

    async def _execute_reorganize(
        self,
        args: dict,
        mutations: list[GraphMutationAction],
    ) -> str:
        """Execute reorganize_graph: apply suggested connections."""
        suggestions = args.get("suggestions", [])
        applied = 0

        for sug in suggestions:
            if sug.get("type") == "connect":
                source_id = sug.get("source_id")
                target_id = sug.get("target_id")
                if not source_id or not target_id:
                    continue
                try:
                    edge = await create_edge(
                        self._db,
                        space_id=self._space_id,
                        source_id=uuid.UUID(source_id),
                        target_id=uuid.UUID(target_id),
                        edge_type=sug.get("edge_type", "parent_child"),
                    )
                    mutations.append(GraphMutationAction(
                        action="add_edge",
                        payload=EdgeResponse.model_validate(edge).model_dump(mode="json"),
                    ))
                    applied += 1
                except Exception:
                    log.warning("Failed to create edge %s→%s", source_id, target_id)

        return json.dumps({
            "status": "ok",
            "applied_suggestions": applied,
            "total_suggestions": len(suggestions),
        })
