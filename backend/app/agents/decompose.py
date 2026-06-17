"""
DecomposeAgent — breaks a goal/milestone into actionable sub-task proposals.

The agent:
1. Builds a prompt from the parent node title, description, and graph context
2. Calls LLMClient.chat_structured with LLMDecomposeOutput as the target schema
3. Post-processes positions (fans nodes horizontally below the parent)
4. Returns a fully populated DecompositionResponse

The LLM is never asked to know about IDs, positions, or DB structure — only
about goal decomposition. The agent bridges between the two worlds.
"""
from __future__ import annotations

import logging
import uuid

from app.core.llm import LLMClient
from app.schemas.ai import DecompositionResponse, LLMDecomposeOutput, SubNodeProposal
from app.schemas.node import NodeLLMView

log = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert goal-decomposition assistant embedded in a visual life-planning canvas.

Your job: break a high-level goal or milestone into concrete, actionable sub-tasks.

Rules:
1. Return ONLY a valid JSON object — no markdown fences, no preamble, no extra text.
2. Sub-tasks must be specific, measurable, and independently completable.
3. node_type values: "goal" (major aspiration), "milestone" (key checkpoint), \
"task" (concrete action), "note" (pure context — no checkbox).
4. priority: use "critical" only for true blockers; default to "medium".
5. Each description should be 1–2 sentences explaining WHY this sub-task matters.
6. tags: lowercase, max 3 per node, directly relevant to the sub-task.
7. Never duplicate or trivially restate the parent goal in a sub-task title.
8. If the goal is already atomic (nothing meaningful to decompose), return an \
empty sub_nodes array with reasoning explaining why.
"""


# ── Message builder ───────────────────────────────────────────────────────────


def _build_messages(
    title: str,
    description: str | None,
    max_children: int,
    context_hint: str | None,
    existing_nodes: list[NodeLLMView],
) -> list[dict]:
    existing_ctx = ""
    if existing_nodes:
        lines = [f"  - {n.title} [{n.node_type}/{n.status}]" for n in existing_nodes[:20]]
        existing_ctx = "\n\nExisting nodes in this canvas (avoid duplicating):\n" + "\n".join(lines)

    hint_line = f"\nUser guidance: {context_hint}" if context_hint else ""

    user_message = (
        f'Goal to decompose: "{title}"\n'
        f"Description: {description or '(none)'}"
        f"{hint_line}"
        f"{existing_ctx}\n\n"
        f"Produce at most {max_children} sub-tasks. "
        "For each, provide title, description, node_type, priority, and tags."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]


# ── Agent ─────────────────────────────────────────────────────────────────────


class DecomposeAgent:
    """
    Stateless agent — create one per request or reuse across requests.
    Pass a pre-configured LLMClient (cloud or local) from the API layer.
    """

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def decompose(
        self,
        parent_node_id: uuid.UUID,
        title: str,
        description: str | None,
        max_children: int = 5,
        context_hint: str | None = None,
        existing_nodes: list[NodeLLMView] | None = None,
    ) -> DecompositionResponse:
        messages = _build_messages(
            title,
            description,
            max_children,
            context_hint,
            existing_nodes or [],
        )

        log.info(
            "DecomposeAgent: decomposing '%s' (max_children=%d model=%s)",
            title,
            max_children,
            self._llm._model,
        )

        output: LLMDecomposeOutput = await self._llm.chat_structured(
            messages, LLMDecomposeOutput
        )

        # ── Post-process: fan nodes horizontally below the parent ──────────
        _assign_positions(output.sub_nodes)

        return DecompositionResponse(
            parent_node_id=parent_node_id,
            sub_nodes=output.sub_nodes,
            suggested_edge_type="parent_child",
            reasoning=output.reasoning,
            provider_used="local" if "ollama" in self._llm._model else "cloud",
            model_used=self._llm._model,
        )


# ── Position helper ───────────────────────────────────────────────────────────


def _assign_positions(nodes: list[SubNodeProposal], y_offset: float = 200.0) -> None:
    """
    Fan sub-nodes horizontally below the parent node.
    With n nodes, node i gets:
        offset_x = (i - (n-1)/2) * HORIZONTAL_STEP
        offset_y = y_offset
    Single node → centred (offset_x = 0).
    """
    n = len(nodes)
    if n == 0:
        return

    HORIZONTAL_STEP = 280.0
    for i, node in enumerate(nodes):
        node.offset_x = (i - (n - 1) / 2) * HORIZONTAL_STEP
        node.offset_y = y_offset
