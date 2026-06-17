/**
 * useGraph — manages the canvas graph state.
 *
 * Responsibilities:
 *  - Load a space graph from the API (falls back to mock data on error)
 *  - Convert backend GoalNode/GoalEdge → Vue Flow Node/Edge
 *  - CRUD: createNode, patchNodePosition, patchNodeStatus
 *  - Keep vfNodes / vfEdges as the single source of truth for the canvas
 */
import { ref, computed } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import { useApi } from './useApi'
import type {
  GoalNode, GoalEdge, GraphResponse,
  NodeCreate, NodeStatus, Position,
} from '@/types/graph'

// ── Converters ────────────────────────────────────────────────────────────────

export function goalNodeToVF(node: GoalNode): Node<GoalNode> {
  // Always favor the database mirrored coordinates (node.x, node.y) over mock defaults or canvas_data hierarchy
  const x = (typeof node.x === 'number') ? node.x : (node.canvas_data?.position?.x ?? 200.0)
  const y = (typeof node.y === 'number') ? node.y : (node.canvas_data?.position?.y ?? 200.0)
  return {
    id: node.id,
    type: 'goalNode',
    position: { x, y },
    data: node,
    style: { width: `${node.canvas_data?.dimensions?.width ?? 220}px` },
  }
}

export function goalEdgeToVF(edge: GoalEdge): Edge<GoalEdge> {
  return {
    id: edge.id,
    source: edge.source_id,
    target: edge.target_id,
    type: 'smartEdge',
    label: edge.label ?? undefined,
    // Solid stroke for all persistent canvas edges!
    animated: false,
    style: { stroke: edge.style.stroke || '#84855c', strokeWidth: edge.style.stroke_width || 2 },
    markerEnd: edge.style.marker_end || 'arrow',
    data: edge,
  }
}

// ── Composable ────────────────────────────────────────────────────────────────

export function useGraph(spaceId: string) {
  const api = useApi()

  const vfNodes = ref<Node<GoalNode>[]>([])
  const vfEdges = ref<Edge<GoalEdge>[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const isMock = ref(false)

  const selectedNodeId = ref<string | null>(null)
  const selectedNode = computed(() => {
    const found = vfNodes.value.find((n: any) => n.id === selectedNodeId.value)
    return (found?.data ?? null) as GoalNode | null
  })

  // ── Load ───────────────────────────────────────────────────────────────────

  async function loadGraph(): Promise<void> {
    isLoading.value = true
    error.value = null
    try {
      const graph = await api.get<GraphResponse>(`/spaces/${spaceId}/graph`)
      _applyGraph(graph)
      isMock.value = false
    } catch (err) {
      // Graceful degradation: do NOT use mock data globally. Show empty space or report actual DB state.
      console.error('[useGraph] Error loading graph:', err)
      error.value = err instanceof Error ? err.message : 'Unknown error'
    } finally {
      isLoading.value = false
    }
  }

  function _applyGraph(graph: GraphResponse) {
    vfNodes.value = graph.nodes.map(goalNodeToVF)
    vfEdges.value = graph.edges.map(goalEdgeToVF)
  }

  // ── Create node ───────────────────────────────────────────────────────────

  async function createNode(
    payload: NodeCreate,
    position: Position,
  ): Promise<GoalNode> {
    const body: NodeCreate = {
      ...payload,
      canvas_data: {
        position,
        dimensions: { width: 240, height: 80 },
        style: { color: '#84855c', icon: null },
        collapsed: false,
      },
    }

    let newNode: GoalNode

    if (isMock.value) {
      // Offline: synthesise a local node so the canvas stays interactive
      newNode = _makeMockNode(body, position)
    } else {
      newNode = await api.post<any>(`/spaces/${spaceId}/nodes`, body) as GoalNode
    }

    vfNodes.value = [...vfNodes.value, goalNodeToVF(newNode) as any]
    return newNode;
  }

  function _makeMockNode(payload: NodeCreate, position: Position): GoalNode {
    const now = new Date().toISOString()
    return {
      id: `local-${Date.now()}`,
      space_id: spaceId,
      title: payload.title,
      description: payload.description ?? null,
      node_type: payload.node_type ?? 'task',
      status: payload.status ?? 'pending',
      priority: payload.priority ?? 'medium',
      tags: payload.tags ?? [],
      due_date: payload.due_date ?? null,
      completed_at: null,
      created_at: now,
      updated_at: now,
      canvas_data: {
        position,
        dimensions: { width: 240, height: 80 },
        style: { color: '#84855c', icon: null },
        collapsed: false,
      },
      ai_provenance: { ai_generated: false, ai_model: null, ai_confidence: null },
    }
  }

  // ── Position PATCH (called on drag-stop) ──────────────────────────────────

  async function patchNodePosition(nodeId: string, position: Position): Promise<void> {
    // Optimistic update: the VF node position is already updated by Vue Flow
    _syncPositionInData(nodeId, position)

    if (isMock.value) return

    try {
      await api.patch(`/spaces/${spaceId}/nodes/${nodeId}/position`, {
        x: position.x,
        y: position.y,
      })
    } catch (err) {
      console.error('[useGraph] Failed to persist position', err)
      // Non-critical — do not roll back, just log
    }
  }

  function _syncPositionInData(nodeId: string, position: Position) {
    const idx = vfNodes.value.findIndex(n => n.id === nodeId)
    if (idx === -1) return
    const node = vfNodes.value[idx]
    if (!node.data) return
    
    // Update both x, y on direct data payload and inner canvas_data.position
    vfNodes.value = vfNodes.value.with(idx, {
      ...node,
      position,
      data: {
        ...node.data,
        x: position.x,
        y: position.y,
        canvas_data: { 
          ...node.data.canvas_data, 
          position: { x: position.x, y: position.y } 
        },
      },
    })
  }

  // ── Status PATCH (checkbox) ───────────────────────────────────────────────

  async function patchNodeStatus(nodeId: string, status: NodeStatus): Promise<void> {
    _syncStatusInData(nodeId, status)

    if (isMock.value) return

    try {
      await api.patch(`/spaces/${spaceId}/nodes/${nodeId}/status`, { status })
    } catch (err) {
      console.error('[useGraph] Failed to persist status', err)
    }
  }

  function _syncStatusInData(nodeId: string, status: NodeStatus) {
    const idx = vfNodes.value.findIndex(n => n.id === nodeId)
    if (idx === -1) return
    const node = vfNodes.value[idx]
    if (!node.data) return
    const completedAt = status === 'completed' ? new Date().toISOString() : null
    vfNodes.value = vfNodes.value.with(idx, {
      ...node,
      data: { ...node.data, status, completed_at: completedAt },
    })
  }

  // ── Full Node Update (from NodeEditor) ────────────────────────────────────

  async function updateNode(nodeId: string, updates: Partial<GoalNode>): Promise<void> {
    // Optimistic update first
    _updateNodeData(nodeId, updates)

    if (isMock.value) return

    try {
      const response = await api.patch<GoalNode>(`/nodes/${nodeId}?space_id=${spaceId}`, updates)
      // Replace with server response to ensure consistency
      _replaceNodeData(nodeId, response)
    } catch (err) {
      console.error('[useGraph] Failed to update node', err)
      // Roll back optimistic update on error
      await loadGraph()
    }
  }

  function _updateNodeData(nodeId: string, updates: Partial<GoalNode>) {
    const idx = vfNodes.value.findIndex(n => n.id === nodeId)
    if (idx === -1) return
    const node = vfNodes.value[idx]
    if (!node.data) return
    vfNodes.value = vfNodes.value.with(idx, {
      ...node,
      data: { ...node.data, ...updates },
    })
  }

  function _replaceNodeData(nodeId: string, newData: GoalNode) {
    const idx = vfNodes.value.findIndex(n => n.id === nodeId)
    if (idx === -1) return
    const node = vfNodes.value[idx]
    vfNodes.value = vfNodes.value.with(idx, {
      ...node,
      data: newData,
    })
  }

  // ── Selection ─────────────────────────────────────────────────────────────

  function selectNode(nodeId: string | null) {
    selectedNodeId.value = nodeId
  }

  /**
   * Delete a node (hard delete by default, so they are physically removed)
   */
  async function deleteNode(nodeId: string, _soft: boolean = false): Promise<GoalNode | undefined> {
    const endpoint = `/nodes/${nodeId}?space_id=${spaceId}&soft=false`
    
    // Store node data for potential undo
    const deletedNode = (vfNodes.value as any[]).find((n: any) => n.id === nodeId)
    
    // Optimistic removal
    vfNodes.value = (vfNodes.value as any[]).filter((n: any) => n.id !== nodeId) as any
    vfEdges.value = (vfEdges.value as any[]).filter((e: any) => e.source !== nodeId && e.target !== nodeId) as any
    
    try {
      await api.delete(endpoint)
    } catch (err: any) {
      error.value = err.message || 'Failed to delete node'
      // Rollback
      await loadGraph()
      throw err
    }
    
    return deletedNode?.data
  }

  return {
    vfNodes,
    vfEdges,
    isLoading,
    error,
    isMock,
    selectedNode,
    selectedNodeId,
    loadGraph,
    createNode,
    patchNodePosition,
    patchNodeStatus,
    updateNode,
    deleteNode,
    selectNode,
  }
}
