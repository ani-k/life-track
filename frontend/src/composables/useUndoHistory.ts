/**
 * useUndoHistory — snapshot-based undo/redo.
 *
 * Each turn stores a full snapshot of vfNodes + vfEdges BEFORE the mutation.
 * Undo restores the snapshot via DB operations, then calls loadGraph().
 * Redo re-applies the original mutations against the DB, then calls loadGraph().
 *
 * This avoids the duplicate-ID problem that occurs when the DB assigns a new
 * UUID on re-create: we always restore the exact original ID.
 */
import { ref } from 'vue'
import type { Ref } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import type { GoalNode, GoalEdge, GraphMutationAction } from '@/types/graph'
import { useApi } from './useApi'

interface NodeSnapshot {
  id: string
  data: GoalNode
  position: { x: number; y: number }
}

interface EdgeSnapshot {
  id: string
  data: GoalEdge
  source: string
  target: string
}

interface Turn {
  /** mutations that were applied (used for redo) */
  mutations: GraphMutationAction[]
  /** full canvas snapshot taken BEFORE the mutations were applied */
  nodesBefore: NodeSnapshot[]
  edgesBefore: EdgeSnapshot[]
}

export function useUndoHistory(
  vfNodes: Ref<Node<GoalNode>[]>,
  vfEdges: Ref<Edge<GoalEdge>[]>,
  spaceId: string,
  loadGraph: () => Promise<void>
) {
  const api = useApi()
  const historyStack = ref<Turn[]>([])
  const redoStack = ref<Turn[]>([])

  // ── snapshot helpers ──────────────────────────────────────────────

  function _snapshotNodes(): NodeSnapshot[] {
    return (vfNodes.value as any[])
      .filter((n: any) => n.type !== 'ghostNode')
      .map((n: any) => ({
        id: n.id,
        data: { ...n.data },
        position: { ...n.position },
      }))
  }

  function _snapshotEdges(): EdgeSnapshot[] {
    return (vfEdges.value as any[]).map((e: any) => ({
      id: e.id,
      data: { ...e.data },
      source: e.source,
      target: e.target,
    }))
  }

  // ── public: call this BEFORE applying mutations to the canvas ─────

  function recordTurn(mutations: GraphMutationAction[]) {
    redoStack.value = []
    historyStack.value.push({
      mutations,
      nodesBefore: _snapshotNodes(),
      edgesBefore: _snapshotEdges(),
    })
  }

  // ── restore snapshot to DB ────────────────────────────────────────

  async function _restoreSnapshot(
    nodesBefore: NodeSnapshot[],
    edgesBefore: EdgeSnapshot[],
    currentNodes: NodeSnapshot[],
    currentEdges: EdgeSnapshot[],
  ) {
    // 1. Delete nodes that appeared after the snapshot
    const beforeNodeIds = new Set(nodesBefore.map(n => n.id))
    const toDeleteNodes = currentNodes.filter(n => !beforeNodeIds.has(n.id))
    for (const n of toDeleteNodes) {
      try {
        await api.delete(`/nodes/${n.id}?space_id=${spaceId}&soft=false`)
      } catch (err) {
        console.error('[undo] delete node failed', n.id, err)
      }
    }

    // 2. Re-create nodes that disappeared after the snapshot
    const currentNodeIds = new Set(currentNodes.map(n => n.id))
    const toCreateNodes = nodesBefore.filter(n => !currentNodeIds.has(n.id))
    for (const n of toCreateNodes) {
      try {
        await api.post(`/spaces/${spaceId}/nodes`, {
          id: n.id,
          title: n.data.title,
          description: n.data.description,
          node_type: n.data.node_type,
          status: n.data.status,
          priority: n.data.priority,
          tags: n.data.tags || [],
          canvas_data: n.data.canvas_data,
        })
      } catch (err) {
        console.error('[undo] create node failed', n.id, err)
      }
    }

    // 3. Restore status changes on nodes that existed in both snapshots
    const currentNodeMap = new Map(currentNodes.map(n => [n.id, n]))
    for (const nb of nodesBefore) {
      const cur = currentNodeMap.get(nb.id)
      if (cur && cur.data.status !== nb.data.status) {
        try {
          await api.patch(`/spaces/${spaceId}/nodes/${nb.id}/status`, {
            status: nb.data.status,
          })
        } catch (err) {
          console.error('[undo] restore status failed', nb.id, err)
        }
      }
    }

    // 4. Delete edges that appeared after the snapshot
    const beforeEdgeIds = new Set(edgesBefore.map(e => e.id))
    const toDeleteEdges = currentEdges.filter(e => !beforeEdgeIds.has(e.id))
    for (const e of toDeleteEdges) {
      try {
        await api.delete(`/spaces/${spaceId}/edges/${e.id}`)
      } catch (err) {
        console.error('[undo] delete edge failed', e.id, err)
      }
    }

    // 5. Re-create edges that disappeared after the snapshot
    const currentEdgeIds = new Set(currentEdges.map(e => e.id))
    const toCreateEdges = edgesBefore.filter(e => !currentEdgeIds.has(e.id))
    for (const e of toCreateEdges) {
      try {
        await api.post(`/spaces/${spaceId}/edges`, {
          source_id: e.data?.source_id ?? e.source,
          target_id: e.data?.target_id ?? e.target,
          edge_type: e.data?.edge_type ?? 'parent_child',
          label: e.data?.label ?? null,
        })
      } catch (err) {
        console.error('[undo] create edge failed', e.id, err)
      }
    }
  }

  // ── triggerUndo ────────────────────────────────────────────────────

  async function triggerUndo(): Promise<string | null> {
    const turn = historyStack.value.pop()
    if (!turn) return null

    const currentNodes = _snapshotNodes()
    const currentEdges = _snapshotEdges()

    await _restoreSnapshot(
      turn.nodesBefore,
      turn.edgesBefore,
      currentNodes,
      currentEdges,
    )

    redoStack.value.push({
      mutations: turn.mutations,
      nodesBefore: currentNodes,
      edgesBefore: currentEdges,
    })

    await loadGraph()
    return 'Действие отменено.'
  }

  // ── triggerRedo ────────────────────────────────────────────────────

  async function triggerRedo(): Promise<string | null> {
    const turn = redoStack.value.pop()
    if (!turn) return null

    // "nodesBefore" in a redo turn is actually the state before undo,
    // i.e. the state we want to get back to.
    const currentNodes = _snapshotNodes()
    const currentEdges = _snapshotEdges()

    await _restoreSnapshot(
      turn.nodesBefore,
      turn.edgesBefore,
      currentNodes,
      currentEdges,
    )

    historyStack.value.push({
      mutations: turn.mutations,
      nodesBefore: currentNodes,
      edgesBefore: currentEdges,
    })

    await loadGraph()
    return 'Действие возвращено.'
  }

  return {
    historyStack,
    redoStack,
    recordTurn,
    triggerUndo,
    triggerRedo,
    canUndo: () => historyStack.value.length > 0,
    canRedo: () => redoStack.value.length > 0,
  }
}
