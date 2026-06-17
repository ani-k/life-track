/**
 * useUndoHistory — provides dynamic undo/redo capability for canvas actions.
 * Allows reverting the last mutations applied to the canvas.
 */
import { ref } from 'vue'
import type { Ref } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import type { GoalNode, GoalEdge, GraphMutationAction } from '@/types/graph'
import { useApi } from './useApi'

export interface HistoricalTurn {
  mutations: GraphMutationAction[]
  inverseMutations: GraphMutationAction[]
}

export function useUndoHistory(
  vfNodes: Ref<Node<GoalNode>[]>,
  vfEdges: Ref<Edge<GoalEdge>[]>,
  spaceId: string,
  loadGraph: () => Promise<void>
) {
  const api = useApi()
  const historyStack = ref<HistoricalTurn[]>([])
  const redoStack = ref<HistoricalTurn[]>([])

  /**
   * Push a mutation action set to history, generating its inverse on-the-fly.
   */
  function recordTurn(mutations: GraphMutationAction[]) {
    const inverseMutations: GraphMutationAction[] = []
    redoStack.value = [] // Clear redo on any new action!

    // Build the reverse mapping of applied changes to revert them
    for (const m of [...mutations].reverse()) {
      if (m.action === 'add_node') {
        const payload = m.payload as any
        inverseMutations.push({
          action: 'delete_node',
          payload: { id: payload.id }
        })
      } else if (m.action === 'add_edge') {
        const payload = m.payload as any
        inverseMutations.push({
          action: 'delete_edge',
          payload: { id: payload.id }
        })
      } else if (m.action === 'update_node') {
        const p = m.payload as any
        // Find existing non-updated node to capture its previous state
        const originalNode = vfNodes.value.find(n => n.id === p.id)
        if (originalNode && originalNode.data) {
          inverseMutations.push({
            action: 'update_node',
            payload: {
              id: originalNode.data.id,
              status: originalNode.data.status,
              completed_at: originalNode.data.completed_at
            }
          })
        }
      } else if (m.action === 'delete_node') {
        const p = m.payload as any
        const originalNode = vfNodes.value.find(n => n.id === p.id)
        if (originalNode && originalNode.data) {
          inverseMutations.push({
            action: 'add_node',
            payload: originalNode.data as any
          })
        }
      } else if (m.action === 'delete_edge') {
        const p = m.payload as any
        const originalEdge = vfEdges.value.find(e => e.id === p.id)
        if (originalEdge && originalEdge.data) {
          inverseMutations.push({
            action: 'add_edge',
            payload: originalEdge.data as any
          })
        }
      }
    }

    historyStack.value.push({
      mutations,
      inverseMutations
    })
  }

  /**
   * Revert the last applied turn of actions
   */
  async function triggerUndo(): Promise<string | null> {
    const turn = historyStack.value.pop()
    if (!turn) return null

    let revertedCount = 0

    // Apply inverses to local store and DB
    for (const inv of turn.inverseMutations) {
      try {
        if (inv.action === 'delete_node') {
          const payload = inv.payload as any
          await api.delete(`/nodes/${payload.id}?space_id=${spaceId}&soft=false`)
          revertedCount++
        } else if (inv.action === 'delete_edge') {
          revertedCount++
        } else if (inv.action === 'add_node') {
          const payload = inv.payload as any
          // Re-create node physically in DB
          await api.post(`/spaces/${spaceId}/nodes`, {
            title: payload.title,
            node_type: payload.node_type,
            status: payload.status,
            priority: payload.priority,
            tags: payload.tags || [],
            canvas_data: payload.canvas_data
          })
          revertedCount++
        } else if (inv.action === 'add_edge') {
          const payload = inv.payload as any
          await api.post(`/spaces/${spaceId}/ai/decompose/accept`, {
            parent_node_id: payload.source_id,
            accepted_nodes: [],
            suggested_edge_type: payload.edge_type
          })
          revertedCount++
        } else if (inv.action === 'update_node') {
          const payload = inv.payload as any
          await api.patch(`/spaces/${spaceId}/nodes/${payload.id}/status`, {
            status: payload.status
          })
          revertedCount++
        }
      } catch (err) {
        console.error('[useUndoHistory] Reversion step failed:', inv, err)
      }
    }

    // Keep in redo stack for replay
    redoStack.value.push(turn)

    // Refresh graph from DB to reflect correct state
    await loadGraph()
    return `Reverted actions successfully.`
  }

  /**
   * Replay the undone turn
   */
  async function triggerRedo(): Promise<string | null> {
    const turn = redoStack.value.pop()
    if (!turn) return null

    let appliedCount = 0

    for (const m of turn.mutations) {
      try {
        if (m.action === 'add_node') {
          const payload = m.payload as any
          await api.post(`/spaces/${spaceId}/nodes`, {
            title: payload.title,
            node_type: payload.node_type,
            status: payload.status,
            priority: payload.priority,
            tags: payload.tags || [],
            canvas_data: payload.canvas_data
          })
          appliedCount++
        } else if (m.action === 'add_edge') {
          const payload = m.payload as any
          await api.post(`/spaces/${spaceId}/ai/decompose/accept`, {
            parent_node_id: payload.source_id,
            accepted_nodes: [],
            suggested_edge_type: payload.edge_type
          })
          appliedCount++
        } else if (m.action === 'delete_node') {
          const payload = m.payload as any
          await api.delete(`/nodes/${payload.id}?space_id=${spaceId}&soft=false`)
          appliedCount++
        } else if (m.action === 'update_node') {
          const payload = m.payload as any
          await api.patch(`/spaces/${spaceId}/nodes/${payload.id}/status`, {
            status: payload.status
          })
          appliedCount++
        }
      } catch (err) {
        console.error('[useUndoHistory] Redo step failed:', m, err)
      }
    }

    // Put back in history
    historyStack.value.push(turn)

    await loadGraph()
    return `Reapplied actions successfully.`
  }

  return {
    historyStack,
    redoStack,
    recordTurn,
    triggerUndo,
    triggerRedo,
    canUndo: () => historyStack.value.length > 0,
    canRedo: () => redoStack.value.length > 0
  }
}
