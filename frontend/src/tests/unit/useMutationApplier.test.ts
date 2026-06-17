/**
 * Tests for useMutationApplier composable.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import type { GoalNode, GoalEdge, GraphMutationAction } from '@/types/graph'

// ── Helpers ────────────────────────────────────────────────────────────────

function makeNode(id: string, title: string, status: GoalNode['status'] = 'pending'): Node<GoalNode> {
  return {
    id,
    type: 'goalNode',
    position: { x: 0, y: 0 },
    data: {
      id,
      title,
      description: null,
      node_type: 'task',
      status,
      priority: 'medium',
      tags: [],
      due_date: null,
      space_id: 'space-1',
      canvas_data: {
        position: { x: 0, y: 0 },
        dimensions: { width: 220, height: 80 },
        style: { color: '#84855c', icon: null },
        collapsed: false,
      },
      ai_provenance: {
        ai_generated: false,
        ai_model: null,
        ai_confidence: null,
        generated_at: null,
      },
      completed_at: null,
      created_at: new Date().toISOString(),
    } as unknown as GoalNode,
  }
}

function makeEdge(id: string, source: string, target: string): Edge<GoalEdge> {
  return {
    id,
    source,
    target,
    type: 'smoothstep',
    data: { id, source_id: source, target_id: target } as unknown as GoalEdge,
  }
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('useMutationApplier', () => {
  beforeEach(() => {
    vi.resetModules()
    // Mock useHighlight to be a no-op (it's a module singleton)
    vi.mock('@/composables/useHighlight', () => ({
      useHighlight: () => ({
        highlightedIds: ref(new Set()),
        highlight: vi.fn(),
      }),
    }))
  })

  it('adds a new node from add_node mutation', async () => {
    const { useMutationApplier } = await import('@/composables/useMutationApplier')
    const vfNodes = ref<Node<GoalNode>[]>([])
    const vfEdges = ref<Edge<GoalEdge>[]>([])
    const { applyMutations } = useMutationApplier(vfNodes, vfEdges, 'space-1')

    const node = makeNode('new-1', 'New Node').data
    const mutations: GraphMutationAction[] = [
      { action: 'add_node', payload: node as unknown as Record<string, unknown> },
    ]

    const result = applyMutations(mutations)
    expect(vfNodes.value).toHaveLength(1)
    expect(vfNodes.value[0].id).toBe('new-1')
    expect(result.summary).toContain('created 1 node')
    expect(result.affectedIds).toContain('new-1')
  })

  it('does not duplicate nodes', async () => {
    const { useMutationApplier } = await import('@/composables/useMutationApplier')
    const existing = makeNode('dup-1', 'Existing')
    const vfNodes = ref<Node<GoalNode>[]>([existing])
    const vfEdges = ref<Edge<GoalEdge>[]>([])
    const { applyMutations } = useMutationApplier(vfNodes, vfEdges, 'space-1')

    applyMutations([{ action: 'add_node', payload: existing.data as unknown as Record<string, unknown> }])
    expect(vfNodes.value).toHaveLength(1)
  })

  it('updates node status from update_node mutation', async () => {
    const { useMutationApplier } = await import('@/composables/useMutationApplier')
    const node = makeNode('n-1', 'My Task', 'pending')
    const vfNodes = ref<Node<GoalNode>[]>([node])
    const vfEdges = ref<Edge<GoalEdge>[]>([])
    const { applyMutations } = useMutationApplier(vfNodes, vfEdges, 'space-1')

    applyMutations([{ action: 'update_node', payload: { id: 'n-1', status: 'completed' } }])
    expect(vfNodes.value[0].data.status).toBe('completed')
  })

  it('adds an edge from add_edge mutation', async () => {
    const { useMutationApplier } = await import('@/composables/useMutationApplier')
    const vfNodes = ref<Node<GoalNode>[]>([makeNode('src', 'Source'), makeNode('tgt', 'Target')])
    const vfEdges = ref<Edge<GoalEdge>[]>([])
    const { applyMutations } = useMutationApplier(vfNodes, vfEdges, 'space-1')

    applyMutations([
      {
        action: 'add_edge',
        payload: {
          id: 'edge-1',
          source_id: 'src',
          target_id: 'tgt',
          edge_type: 'parent_child',
          label: null,
          style: { stroke: '#84855c', stroke_width: 2, marker_end: 'arrow', animated: true },
          ai_generated: true,
          space_id: 'space-1',
          target_space_id: null,
          created_at: new Date().toISOString(),
        },
      },
    ])
    expect(vfEdges.value).toHaveLength(1)
    expect(vfEdges.value[0].source).toBe('src')
    expect(vfEdges.value[0].target).toBe('tgt')
  })

  it('deletes a node from delete_node mutation', async () => {
    const { useMutationApplier } = await import('@/composables/useMutationApplier')
    const n1 = makeNode('del-1', 'To Delete')
    const n2 = makeNode('keep-1', 'Keep Me')
    const vfNodes = ref<Node<GoalNode>[]>([n1, n2])
    const vfEdges = ref<Edge<GoalEdge>[]>([makeEdge('e1', 'del-1', 'keep-1')])
    const { applyMutations } = useMutationApplier(vfNodes, vfEdges, 'space-1')

    applyMutations([{ action: 'delete_node', payload: { id: 'del-1' } }])
    expect(vfNodes.value).toHaveLength(1)
    expect(vfNodes.value[0].id).toBe('keep-1')
    // Edge connected to deleted node should also be removed
    expect(vfEdges.value).toHaveLength(0)
  })

  it('deletes an edge from delete_edge mutation', async () => {
    const { useMutationApplier } = await import('@/composables/useMutationApplier')
    const vfNodes = ref<Node<GoalNode>[]>([])
    const vfEdges = ref<Edge<GoalEdge>[]>([makeEdge('e-del', 'a', 'b'), makeEdge('e-keep', 'c', 'd')])
    const { applyMutations } = useMutationApplier(vfNodes, vfEdges, 'space-1')

    applyMutations([{ action: 'delete_edge', payload: { id: 'e-del' } }])
    expect(vfEdges.value).toHaveLength(1)
    expect(vfEdges.value[0].id).toBe('e-keep')
  })

  it('returns empty summary when no mutations', async () => {
    const { useMutationApplier } = await import('@/composables/useMutationApplier')
    const { applyMutations } = useMutationApplier(ref([]), ref([]), 'space-1')
    const result = applyMutations([])
    expect(result.summary).toBe('')
    expect(result.affectedIds).toHaveLength(0)
  })

  it('summarises multiple mutation types', async () => {
    const { useMutationApplier } = await import('@/composables/useMutationApplier')
    const existingNode = makeNode('upd-1', 'Existing', 'pending')
    const vfNodes = ref<Node<GoalNode>[]>([existingNode])
    const vfEdges = ref<Edge<GoalEdge>[]>([])
    const { applyMutations } = useMutationApplier(vfNodes, vfEdges, 'space-1')

    const newNodeData = makeNode('new-2', 'Fresh Node').data
    applyMutations([
      { action: 'add_node', payload: newNodeData as unknown as Record<string, unknown> },
      { action: 'update_node', payload: { id: 'upd-1', status: 'in_progress' } },
    ])
    expect(vfNodes.value).toHaveLength(2)
    const result = applyMutations([])
    expect(result.summary).toBe('')
  })
})
