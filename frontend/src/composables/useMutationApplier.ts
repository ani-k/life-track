/**
 * useMutationApplier — applies AI-generated graph mutations to the canvas.
 *
 * Receives the vfNodes / vfEdges refs from GoalCanvas and mutates them
 * optimistically. Calls useHighlight to pulse-animate affected nodes.
 */
import type { Ref } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import { goalNodeToVF, goalEdgeToVF } from './useGraph'
import { useHighlight } from './useHighlight'
import type { GoalNode, GoalEdge, GraphMutationAction } from '@/types/graph'

export interface ApplyResult {
  summary: string
  affectedIds: string[]
}

export function useMutationApplier(
  vfNodes: Ref<Node<GoalNode>[]>,
  vfEdges: Ref<Edge<GoalEdge>[]>,
  _spaceId: string, // reserved for future DB sync
) {
  const { highlight } = useHighlight()

  function applyMutations(mutations: GraphMutationAction[]): ApplyResult {
    const affectedIds: string[] = []
    let addedNodes = 0
    let updatedNodes = 0
    let addedEdges = 0

    for (const m of mutations) {
      try {
        if (m.action === 'add_node') {
          const payload = m.payload as unknown as GoalNode
          if (!vfNodes.value.find((n) => n.id === payload.id)) {
            vfNodes.value = [...vfNodes.value, goalNodeToVF(payload)]
            affectedIds.push(payload.id)
            addedNodes++
          }
        } else if (m.action === 'update_node') {
          const p = m.payload as unknown as { id: string; status?: string; completed_at?: string | null }
          vfNodes.value = vfNodes.value.map((n) => {
            if (n.id !== p.id) return n
            if (!n.data) return n
            const updated: GoalNode = { ...n.data }
            if (p.status !== undefined) updated.status = p.status as GoalNode['status']
            if ('completed_at' in p) updated.completed_at = p.completed_at ?? null
            affectedIds.push(n.id)
            updatedNodes++
            return { ...n, data: updated }
          })
        } else if (m.action === 'add_edge') {
          const payload = m.payload as unknown as GoalEdge
          if (!vfEdges.value.find((e) => e.id === payload.id)) {
            vfEdges.value = [...vfEdges.value, goalEdgeToVF(payload)]
            affectedIds.push(payload.source_id, payload.target_id)
            addedEdges++
          }
        } else if (m.action === 'delete_node') {
          const p = m.payload as { id: string }
          vfNodes.value = vfNodes.value.filter((n) => n.id !== p.id)
          vfEdges.value = vfEdges.value.filter(
            (e) => e.source !== p.id && e.target !== p.id,
          )
        } else if (m.action === 'delete_edge') {
          const p = m.payload as { id: string }
          vfEdges.value = vfEdges.value.filter((e) => e.id !== p.id)
        }
      } catch (err) {
        console.error('[useMutationApplier] failed to apply mutation:', m, err)
      }
    }

    const uniqueIds = [...new Set(affectedIds)]
    if (uniqueIds.length > 0) highlight(uniqueIds)

    const parts: string[] = []
    if (addedNodes > 0) parts.push(`created ${addedNodes} node${addedNodes > 1 ? 's' : ''}`)
    if (updatedNodes > 0) parts.push(`updated ${updatedNodes} node${updatedNodes > 1 ? 's' : ''}`)
    if (addedEdges > 0) parts.push(`added ${addedEdges} edge${addedEdges > 1 ? 's' : ''}`)

    return {
      summary: parts.length > 0 ? `AI ${parts.join(', ')}` : '',
      affectedIds: uniqueIds,
    }
  }

  return { applyMutations }
}
