/**
 * Unit tests for useGraph composable.
 *
 * Covers: load with API success, mock fallback on error,
 * createNode (mock + API paths), patchNodePosition, patchNodeStatus,
 * edge cases: empty graph, invalid nodeId.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mockGraph, MOCK_SPACE_ID } from '@/data/mockGraph'
import { goalNodeToVF, goalEdgeToVF } from '@/composables/useGraph'

// ── Isolate fetch globally ────────────────────────────────────────────
let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  global.fetch = fetchMock
  localStorage.clear()
})

// ── Helpers ───────────────────────────────────────────────────────────
function mockFetchOk(body: unknown, status = 200) {
  fetchMock.mockResolvedValueOnce({
    ok: true,
    status,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(''),
  } as Response)
}

function mockFetchFail(status = 500) {
  fetchMock.mockResolvedValueOnce({
    ok: false,
    status,
    text: () => Promise.resolve('Internal Server Error'),
  } as Response)
}

function mockFetchNetworkError() {
  fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
}

// We import useGraph inside each test to get a fresh reactive state
async function freshGraph(spaceId = MOCK_SPACE_ID) {
  // Dynamic import gives a fresh module instance per test
  const { useGraph } = await import('@/composables/useGraph')
  return useGraph(spaceId)
}

// ── Tests ─────────────────────────────────────────────────────────────

describe('goalNodeToVF', () => {
  it('maps node_type to "goalNode"', () => {
    const node = mockGraph.nodes[0]
    const vf = goalNodeToVF(node)
    expect(vf.type).toBe('goalNode')
  })

  it('uses canvas_data.position as VF position', () => {
    const node = mockGraph.nodes[0]
    const vf = goalNodeToVF(node)
    expect(vf.position).toEqual(node.canvas_data.position)
  })

  it('stores full GoalNode in data', () => {
    const node = mockGraph.nodes[0]
    const vf = goalNodeToVF(node)
    expect(vf.data).toBe(node)
  })
})

describe('goalEdgeToVF', () => {
  it('maps source_id / target_id to source / target', () => {
    const edge = mockGraph.edges[0]
    const vf = goalEdgeToVF(edge)
    expect(vf.source).toBe(edge.source_id)
    expect(vf.target).toBe(edge.target_id)
  })

  it('animates AI-generated edges', () => {
    const aiEdge = mockGraph.edges.find(e => e.ai_generated)!
    expect(goalEdgeToVF(aiEdge).animated).toBe(true)
  })

  it('uses smoothstep for parent_child edges', () => {
    const edge = mockGraph.edges.find(e => e.edge_type === 'parent_child')!
    expect(goalEdgeToVF(edge).type).toBe('smoothstep')
  })
})

describe('useGraph.loadGraph', () => {
  it('populates vfNodes and vfEdges on API success', async () => {
    mockFetchOk(mockGraph)
    const graph = await freshGraph()
    await graph.loadGraph()

    expect(graph.vfNodes.value).toHaveLength(mockGraph.nodes.length)
    expect(graph.vfEdges.value).toHaveLength(mockGraph.edges.length)
    expect(graph.isMock.value).toBe(false)
  })

  it('falls back to mock data on network error', async () => {
    mockFetchNetworkError()
    const graph = await freshGraph()
    await graph.loadGraph()

    expect(graph.vfNodes.value).toHaveLength(mockGraph.nodes.length)
    expect(graph.isMock.value).toBe(true)
    expect(graph.error.value).toBeNull()
  })

  it('falls back to mock data on 500 error', async () => {
    mockFetchFail(500)
    const graph = await freshGraph()
    await graph.loadGraph()

    expect(graph.isMock.value).toBe(true)
  })

  it('handles empty graph (0 nodes, 0 edges)', async () => {
    mockFetchOk({ ...mockGraph, nodes: [], edges: [] })
    const graph = await freshGraph()
    await graph.loadGraph()

    expect(graph.vfNodes.value).toHaveLength(0)
    expect(graph.vfEdges.value).toHaveLength(0)
  })

  it('sets isLoading to false after completion', async () => {
    mockFetchOk(mockGraph)
    const graph = await freshGraph()
    const p = graph.loadGraph()
    expect(graph.isLoading.value).toBe(true)
    await p
    expect(graph.isLoading.value).toBe(false)
  })
})

describe('useGraph.createNode', () => {
  const pos = { x: 100, y: 200 }

  it('adds a node to vfNodes on success', async () => {
    const newNode = { ...mockGraph.nodes[0], id: 'new-1', title: 'New Goal' }
    mockFetchOk(mockGraph)  // loadGraph
    mockFetchOk(newNode)    // POST /nodes

    const graph = await freshGraph()
    await graph.loadGraph()
    const before = graph.vfNodes.value.length

    await graph.createNode({ title: 'New Goal' }, pos)
    expect(graph.vfNodes.value).toHaveLength(before + 1)
  })

  it('creates a mock node when isMock=true without calling fetch', async () => {
    mockFetchNetworkError()  // loadGraph → mock fallback
    const graph = await freshGraph()
    await graph.loadGraph()

    const fetchCallCount = fetchMock.mock.calls.length
    await graph.createNode({ title: 'Offline Task' }, pos)

    // No additional fetch calls
    expect(fetchMock.mock.calls.length).toBe(fetchCallCount)
    expect(graph.vfNodes.value.some(n => n.data.title === 'Offline Task')).toBe(true)
  })

  it('mock node has correct default values', async () => {
    mockFetchNetworkError()
    const graph = await freshGraph()
    await graph.loadGraph()

    await graph.createNode({ title: 'X', node_type: 'milestone' }, pos)
    const added = graph.vfNodes.value.find(n => n.data.title === 'X')!
    expect(added.data.node_type).toBe('milestone')
    expect(added.data.status).toBe('pending')
    expect(added.data.ai_provenance.ai_generated).toBe(false)
  })
})

describe('useGraph.patchNodePosition', () => {
  it('syncs position in canvas_data.position', async () => {
    mockFetchOk(mockGraph)
    mockFetchOk(undefined, 204)  // PATCH response
    const graph = await freshGraph()
    await graph.loadGraph()

    const nodeId = graph.vfNodes.value[0].id
    await graph.patchNodePosition(nodeId, { x: 999, y: 888 })

    const updated = graph.vfNodes.value.find(n => n.id === nodeId)!
    expect(updated.data.canvas_data.position).toEqual({ x: 999, y: 888 })
  })

  it('does not throw on invalid nodeId', async () => {
    mockFetchOk(mockGraph)
    const graph = await freshGraph()
    await graph.loadGraph()
    await expect(graph.patchNodePosition('non-existent', { x: 0, y: 0 })).resolves.not.toThrow()
  })
})

describe('useGraph.patchNodeStatus', () => {
  it('updates status to completed', async () => {
    mockFetchOk(mockGraph)
    mockFetchOk(undefined, 204)
    const graph = await freshGraph()
    await graph.loadGraph()

    const nodeId = graph.vfNodes.value[0].id
    await graph.patchNodeStatus(nodeId, 'completed')

    const updated = graph.vfNodes.value.find(n => n.id === nodeId)!
    expect(updated.data.status).toBe('completed')
    expect(updated.data.completed_at).not.toBeNull()
  })

  it('clears completed_at when toggling back to pending', async () => {
    mockFetchOk(mockGraph)
    mockFetchOk(undefined, 204)
    mockFetchOk(undefined, 204)
    const graph = await freshGraph()
    await graph.loadGraph()

    const nodeId = graph.vfNodes.value[0].id
    await graph.patchNodeStatus(nodeId, 'completed')
    await graph.patchNodeStatus(nodeId, 'pending')

    const updated = graph.vfNodes.value.find(n => n.id === nodeId)!
    expect(updated.data.status).toBe('pending')
    expect(updated.data.completed_at).toBeNull()
  })
})

describe('useGraph.selectNode', () => {
  it('sets selectedNode to the matching GoalNode', async () => {
    mockFetchOk(mockGraph)
    const graph = await freshGraph()
    await graph.loadGraph()

    const id = graph.vfNodes.value[0].id
    graph.selectNode(id)
    expect(graph.selectedNode.value?.id).toBe(id)
  })

  it('clears selectedNode when called with null', async () => {
    mockFetchOk(mockGraph)
    const graph = await freshGraph()
    await graph.loadGraph()

    graph.selectNode(graph.vfNodes.value[0].id)
    graph.selectNode(null)
    expect(graph.selectedNode.value).toBeNull()
  })
})
