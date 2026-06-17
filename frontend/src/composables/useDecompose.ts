/**
 * useDecompose — manages the AI decomposition flow.
 *
 * Flow:
 *  1. triggerDecompose(parentNodeId) → POST /ai/decompose → ghost nodes added to vfNodes
 *  2. User sees GhostNode cards (50% opacity) with Accept/Discard buttons
 *  3. acceptProposal(ghostId) → POST /ai/decompose/accept (or mock) → real node
 *  4. discardProposal(ghostId) → remove ghost node
 *
 * Ghost nodes live in the main vfNodes array with type="ghostNode".
 * The drag-stop handler in GoalCanvas skips them (type check).
 */
import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import { useApi, ApiError } from './useApi'
import { goalNodeToVF, goalEdgeToVF } from './useGraph'
import type { GoalNode, GoalEdge, SubNodeProposal, DecompositionResponse, Provider } from '@/types/graph'

import { layoutTree } from './useLayout'

// ── Ghost node data shape ─────────────────────────────────────────────────────

export interface GhostNodeData {
  isGhost: true
  proposal: SubNodeProposal
  parentNodeId: string
}

// ── Composable ────────────────────────────────────────────────────────────────

export function useDecompose(
  spaceId: string,
  vfNodes: Ref<Node[]>,
  vfEdges: Ref<Edge[]>,
  isMock: Ref<boolean>,
  provider: Ref<Provider>,
  localModel: Ref<string>,
) {
  const api = useApi()
  const isDecomposing = ref(false)
  const decompositionError = ref<string | null>(null)

  const ghostCount = computed(
    () => vfNodes.value.filter(n => n.type === 'ghostNode').length
  )

  // ── Auto-Layout for whole tree ─────────────────────────────────────
  
  function applyTreeLayout() {
    // 1. Prepare simple representations
    const layoutNodes = vfNodes.value.map(n => ({
      id: n.id,
      width: 220,
      height: 80,
    }))
    const layoutEdges = vfEdges.value.map(e => ({
      source: e.source,
      target: e.target,
    }))

    // 2. Perform Dagre Layout
    const results = layoutTree(layoutNodes, layoutEdges, 'TB')

    // 3. Shift coords so they don't jump too wildly — anchor parent node to its original pos
    results.forEach(res => {
      const targetNode = vfNodes.value.find(n => n.id === res.id)
      if (targetNode) {
        targetNode.position = { x: res.x, y: res.y }
        // Save to DB (only for real, non-ghost nodes)
        if (targetNode.type !== 'ghostNode' && !isMock.value) {
          api.patch(`/spaces/${spaceId}/nodes/${targetNode.id}/position`, {
            position: { x: res.x, y: res.y },
          }).catch(err => console.error('[useDecompose] Layout save failed', err))
        }
      }
    })
  }

  // ── Internal: add ghost nodes to canvas ────────────────────────────

  function _addGhostNodes(
    parentId: string,
    parentPosition: { x: number; y: number },
    proposals: SubNodeProposal[],
  ): void {
    // Dynamic generation of ghost node list
    // Dynamic generation of ghost node list
    const ghosts: Node<GhostNodeData>[] = proposals.map((p, i) => {
      const gId = `ghost-${parentId}-${i}-${Date.now()}`
      return {
        id: gId,
        type: 'ghostNode',
        position: {
          x: parentPosition.x,
          y: parentPosition.y,
        },
        data: {
          isGhost: true as const,
          proposal: p,
          parentNodeId: parentId,
        },
        draggable: true,
        selectable: false,
      }
    })

    vfNodes.value = [...vfNodes.value, ...ghosts]

    // Create virtual ghost connection edges in the background to feed Dagre auto-layout
    const ghostEdges: Edge[] = proposals.map((_p, i) => {
      const gId = ghosts[i].id
      return {
        id: `e-ghost-${parentId}-${gId}`,
        source: parentId,
        target: gId,
        type: 'smartEdge',
        animated: true,
        style: { stroke: '#d97706', strokeWidth: 2, strokeDasharray: '5,5' },
      }
    })
    
    // Inject temp edges for layout calculation representation
    const originalEdgesLength = vfEdges.value.length
    vfEdges.value = [...vfEdges.value, ...ghostEdges]

    // Calculate layout for all nodes at once (tree top-to-bottom layout)
    applyTreeLayout()

    // Clean up temporary ghost illustration edges (keep only real ones)
    vfEdges.value = vfEdges.value.slice(0, originalEdgesLength)
  }

  // ── triggerDecompose ─────────────────────────────────────────────────

  async function triggerDecompose(parentNodeId: string): Promise<void> {
    if (isDecomposing.value) return
    isDecomposing.value = true
    decompositionError.value = null

    // Remove any existing ghosts for this parent first (re-decompose)
    _removeGhostsForParent(parentNodeId)

    // Find parent position for absolute placement
    const parentVF = vfNodes.value.find(n => n.id === parentNodeId)
    const parentPosition = parentVF?.position ?? { x: 200, y: 200 }

    try {
      if (isMock.value) {
        // Offline mode: generate local mock proposals
        const mockProposals = _mockProposals(
          (parentVF?.data as GoalNode)?.title ?? 'Goal'
        )
        _addGhostNodes(parentNodeId, parentPosition, mockProposals)
        return
      }

      const response = await api.post<DecompositionResponse>(
        `/spaces/${spaceId}/ai/decompose`,
        {
          node_id: parentNodeId,
          provider: provider.value,
          local_model: provider.value === 'local' ? localModel.value : null,
          max_children: 5,
        },
      )
      _addGhostNodes(parentNodeId, parentPosition, response.sub_nodes)
    } catch (err) {
      if (err instanceof ApiError || err instanceof TypeError) {
        // API unavailable — fall back to mock proposals
        console.warn('[useDecompose] API unavailable, using mock proposals')
        const mockProposals = _mockProposals(
          (parentVF?.data as GoalNode)?.title ?? 'Goal'
        )
        _addGhostNodes(parentNodeId, parentPosition, mockProposals)
      } else {
        decompositionError.value = err instanceof Error ? err.message : 'Decompose failed'
      }
    } finally {
      isDecomposing.value = false
    }
  }

  // ── acceptProposal ───────────────────────────────────────────────────

  async function acceptProposal(ghostId: string): Promise<void> {
    const ghostVF = vfNodes.value.find(n => n.id === ghostId)
    if (!ghostVF || ghostVF.type !== 'ghostNode') return

    const { proposal, parentNodeId } = ghostVF.data as GhostNodeData
    
    // Use current updated auto-layout position
    const parentVF = vfNodes.value.find(n => n.id === parentNodeId)
    const parentPosition = parentVF?.position ?? { x: 0, y: 0 }
    const ghostPosition = ghostVF.position

    // Optimistically remove ghost immediately
    vfNodes.value = vfNodes.value.filter(n => n.id !== ghostId)

    const now = new Date().toISOString()

    if (isMock.value) {
      // Convert ghost → real node locally
      const newGoalNode: GoalNode = _proposalToGoalNode(
        proposal, spaceId, ghostPosition, now
      )
      vfNodes.value = [...vfNodes.value, goalNodeToVF(newGoalNode)]
      _addEdgeLocally(parentNodeId, newGoalNode.id, now)
      return
    }

    try {
      const response = await api.post<{ created_nodes: GoalNode[]; created_edges: GoalEdge[] }>(
        `/spaces/${spaceId}/ai/decompose/accept`,
        {
          parent_node_id: parentNodeId,
          accepted_nodes: [{
            ...proposal,
            // Pass the calculated auto-layout coordinates as offset relative to parent
            offset_x: ghostPosition.x - parentPosition.x,
            offset_y: ghostPosition.y - parentPosition.y,
          }],
          parent_position: parentPosition,
          suggested_edge_type: 'parent_child',
        },
      )
      for (const n of response.created_nodes) {
        vfNodes.value = [...vfNodes.value, goalNodeToVF(n)]
      }
      for (const e of response.created_edges) {
        vfEdges.value = [...vfEdges.value, goalEdgeToVF(e)]
      }
    } catch {
      // Fallback: persist locally even if API fails
      const newGoalNode = _proposalToGoalNode(proposal, spaceId, ghostPosition, now)
      vfNodes.value = [...vfNodes.value, goalNodeToVF(newGoalNode)]
      _addEdgeLocally(parentNodeId, newGoalNode.id, now)
    }
  }

  // ── acceptAll ────────────────────────────────────────────────────────

  async function acceptAll(): Promise<void> {
    const ghostIds = vfNodes.value
      .filter(n => n.type === 'ghostNode')
      .map(n => n.id)
    // Process sequentially to preserve order
    for (const id of ghostIds) {
      await acceptProposal(id)
    }
  }

  // ── discardProposal ──────────────────────────────────────────────────

  function discardProposal(ghostId: string): void {
    vfNodes.value = vfNodes.value.filter(n => n.id !== ghostId)
  }

  function discardAll(): void {
    vfNodes.value = vfNodes.value.filter(n => n.type !== 'ghostNode')
  }

  // ── Helpers ───────────────────────────────────────────────────────────

  function _removeGhostsForParent(parentId: string): void {
    vfNodes.value = vfNodes.value.filter(n => {
      if (n.type !== 'ghostNode') return true
      return (n.data as GhostNodeData).parentNodeId !== parentId
    })
  }

  function _addEdgeLocally(sourceId: string, targetId: string, now: string): void {
    const edge: GoalEdge = {
      id: `e-${Date.now()}`,
      space_id: spaceId,
      source_id: sourceId,
      target_id: targetId,
      target_space_id: null,
      edge_type: 'parent_child',
      label: null,
      style: { animated: true, stroke: '#84855c', stroke_width: 2, marker_end: 'arrow' },
      ai_generated: true,
      created_at: now,
      updated_at: now,
    }
    vfEdges.value = [...vfEdges.value, goalEdgeToVF(edge)]
  }

  function _proposalToGoalNode(
    proposal: SubNodeProposal,
    spaceId: string,
    targetPosition: { x: number; y: number },
    now: string,
  ): GoalNode {
    return {
      id: `ai-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      space_id: spaceId,
      title: proposal.title,
      description: proposal.description ?? null,
      node_type: proposal.node_type,
      status: 'pending',
      priority: proposal.priority,
      tags: proposal.tags,
      due_date: null,
      completed_at: null,
      created_at: now,
      updated_at: now,
      canvas_data: {
        position: {
          x: targetPosition.x,
          y: targetPosition.y,
        },
        dimensions: { width: 220, height: 80 },
        style: { color: '#84855c', icon: null },
        collapsed: false,
      },
      ai_provenance: {
        ai_generated: true,
        ai_model: provider.value === 'local' ? `ollama/${localModel.value}` : 'gpt-4o',
        ai_confidence: 0.85,
      },
    }
  }

  function _mockProposals(parentTitle: string): SubNodeProposal[] {
    const templates = [
      { title: `Research & planning for: ${parentTitle}`, node_type: 'task' as const, priority: 'high' as const },
      { title: 'Define success criteria and milestones', node_type: 'milestone' as const, priority: 'medium' as const },
      { title: 'Identify required resources', node_type: 'task' as const, priority: 'medium' as const },
      { title: 'Build first working prototype', node_type: 'task' as const, priority: 'high' as const },
      { title: 'Review and iterate', node_type: 'task' as const, priority: 'low' as const },
    ]
    const n = templates.length
    return templates.map((t, i) => ({
      ...t,
      description: null,
      tags: [],
      offset_x: (i - (n - 1) / 2) * 280,
      offset_y: 200,
    }))
  }

  return {
    isDecomposing,
    decompositionError,
    ghostCount,
    triggerDecompose,
    acceptProposal,
    discardProposal,
    acceptAll,
    discardAll,
  }
}
