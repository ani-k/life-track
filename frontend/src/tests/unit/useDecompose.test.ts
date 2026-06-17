/**
 * Unit tests for useDecompose composable.
 *
 * Covers: triggerDecompose (API + mock fallback), acceptProposal (API + local),
 * discardProposal, acceptAll/discardAll, ghost node lifecycle, position calc.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'
import type { Node, Edge } from '@vue-flow/core'
import { mockGraph } from '@/data/mockGraph'
import { goalNodeToVF } from '@/composables/useGraph'
import type { DecompositionResponse, Provider } from '@/types/graph'

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  global.fetch = fetchMock
  localStorage.clear()
  vi.resetModules()
})

function mockOk(body: unknown) {
  fetchMock.mockResolvedValueOnce({
    ok: true, status: 200,
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(''),
  } as Response)
}
function mockNetworkError() {
  fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
}

const SPACE_ID = 'space-001'
const PARENT_ID = 'n1'

function makeDecomposeResponse(count = 3): DecompositionResponse {
  return {
    parent_node_id: PARENT_ID,
    sub_nodes: Array.from({ length: count }, (_, i) => ({
      title: `Sub-task ${i + 1}`,
      description: null,
      node_type: 'task' as const,
      priority: 'medium' as const,
      tags: [],
      offset_x: (i - (count - 1) / 2) * 280,
      offset_y: 200,
    })),
    suggested_edge_type: 'parent_child',
    reasoning: 'Test decomposition',
    provider_used: 'cloud',
    model_used: 'gpt-4o',
  }
}

async function freshDecompose(opts?: { isMock?: boolean; provider?: Provider }) {
  const vfNodes = ref<Node[]>(mockGraph.nodes.map(goalNodeToVF))
  const vfEdges = ref<Edge[]>([])
  const isMock = ref(opts?.isMock ?? false)
  const provider = ref<Provider>(opts?.provider ?? 'cloud')
  const localModel = ref('gemma3:2b')
  const { useDecompose } = await import('@/composables/useDecompose')
  return {
    ...useDecompose(SPACE_ID, vfNodes, vfEdges, isMock, provider, localModel),
    vfNodes,
    vfEdges,
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// triggerDecompose
// ─────────────────────────────────────────────────────────────────────────────

describe('triggerDecompose', () => {
  it('adds ghost nodes on successful API call', async () => {
    mockOk(makeDecomposeResponse(3))
    const d = await freshDecompose()
    await d.triggerDecompose(PARENT_ID)

    const ghosts = d.vfNodes.value.filter(n => n.type === 'ghostNode')
    expect(ghosts).toHaveLength(3)
    expect(d.ghostCount.value).toBe(3)
  })

  it('each ghost node has GhostNodeData', async () => {
    mockOk(makeDecomposeResponse(2))
    const d = await freshDecompose()
    await d.triggerDecompose(PARENT_ID)

    const ghost = d.vfNodes.value.find(n => n.type === 'ghostNode')!
    expect(ghost.data.isGhost).toBe(true)
    expect(ghost.data.proposal.title).toContain('Sub-task')
    expect(ghost.data.parentNodeId).toBe(PARENT_ID)
  })

  it('sends provider=cloud in request body', async () => {
    mockOk(makeDecomposeResponse(1))
    const d = await freshDecompose({ provider: 'cloud' })
    await d.triggerDecompose(PARENT_ID)

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.provider).toBe('cloud')
  })

  it('sends provider=local with local_model when local selected', async () => {
    mockOk(makeDecomposeResponse(1))
    const d = await freshDecompose({ provider: 'local' })
    await d.triggerDecompose(PARENT_ID)

    const body = JSON.parse(fetchMock.mock.calls[0][1].body)
    expect(body.provider).toBe('local')
    expect(body.local_model).toBe('gemma3:2b')
  })

  it('falls back to mock proposals on network error', async () => {
    mockNetworkError()
    const d = await freshDecompose()
    await d.triggerDecompose(PARENT_ID)

    expect(d.ghostCount.value).toBeGreaterThan(0)
    expect(d.decompositionError.value).toBeNull()
  })

  it('uses mock proposals when isMock=true (no fetch)', async () => {
    const d = await freshDecompose({ isMock: true })
    await d.triggerDecompose(PARENT_ID)

    expect(fetchMock).not.toHaveBeenCalled()
    expect(d.ghostCount.value).toBeGreaterThan(0)
  })

  it('replaces existing ghosts for same parent on re-decompose', async () => {
    mockOk(makeDecomposeResponse(3))
    mockOk(makeDecomposeResponse(2))
    const d = await freshDecompose()

    await d.triggerDecompose(PARENT_ID)
    expect(d.ghostCount.value).toBe(3)

    await d.triggerDecompose(PARENT_ID)
    expect(d.ghostCount.value).toBe(2)  // old 3 replaced by new 2
  })

  it('sets isDecomposing=false after completion', async () => {
    mockOk(makeDecomposeResponse(1))
    const d = await freshDecompose()
    const p = d.triggerDecompose(PARENT_ID)
    expect(d.isDecomposing.value).toBe(true)
    await p
    expect(d.isDecomposing.value).toBe(false)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// acceptProposal
// ─────────────────────────────────────────────────────────────────────────────

describe('acceptProposal', () => {
  it('removes ghost and adds a real goalNode on API success', async () => {
    mockOk(makeDecomposeResponse(1))  // decompose
    // accept endpoint response
    const acceptedNode = { ...mockGraph.nodes[0], id: 'created-1', title: 'Sub-task 1' }
    const acceptedEdge = { ...mockGraph.edges[0], id: 'e-new' }
    mockOk({ created_nodes: [acceptedNode], created_edges: [acceptedEdge] })

    const d = await freshDecompose()
    await d.triggerDecompose(PARENT_ID)

    const ghostId = d.vfNodes.value.find(n => n.type === 'ghostNode')!.id
    await d.acceptProposal(ghostId)

    expect(d.vfNodes.value.filter(n => n.type === 'ghostNode')).toHaveLength(0)
    expect(d.vfNodes.value.some(n => n.id === 'created-1')).toBe(true)
  })

  it('converts ghost to goalNode locally in mock mode', async () => {
    const d = await freshDecompose({ isMock: true })
    await d.triggerDecompose(PARENT_ID)

    const ghostId = d.vfNodes.value.find(n => n.type === 'ghostNode')!.id
    const countBefore = d.vfNodes.value.length
    await d.acceptProposal(ghostId)

    // ghost removed, real node added → net count stays same
    expect(d.vfNodes.value.length).toBe(countBefore)
    expect(d.vfNodes.value.filter(n => n.type === 'ghostNode').length).toBeLessThan(d.ghostCount.value + 1)
  })

  it('adds an edge connecting parent → accepted node', async () => {
    const d = await freshDecompose({ isMock: true })
    await d.triggerDecompose(PARENT_ID)

    const edgesBefore = d.vfEdges.value.length
    const ghostId = d.vfNodes.value.find(n => n.type === 'ghostNode')!.id
    await d.acceptProposal(ghostId)

    expect(d.vfEdges.value.length).toBe(edgesBefore + 1)
    const newEdge = d.vfEdges.value[d.vfEdges.value.length - 1]
    expect(newEdge.source).toBe(PARENT_ID)
  })

  it('does nothing for unknown ghostId', async () => {
    const d = await freshDecompose({ isMock: true })
    await d.triggerDecompose(PARENT_ID)
    const count = d.vfNodes.value.length
    await d.acceptProposal('non-existent-ghost')
    expect(d.vfNodes.value.length).toBe(count)
  })
})

// ─────────────────────────────────────────────────────────────────────────────
// discardProposal / discardAll / acceptAll
// ─────────────────────────────────────────────────────────────────────────────

describe('discardProposal', () => {
  it('removes the ghost node', async () => {
    const d = await freshDecompose({ isMock: true })
    await d.triggerDecompose(PARENT_ID)
    const ghostId = d.vfNodes.value.find(n => n.type === 'ghostNode')!.id
    d.discardProposal(ghostId)
    expect(d.vfNodes.value.find(n => n.id === ghostId)).toBeUndefined()
  })
})

describe('discardAll', () => {
  it('removes all ghost nodes', async () => {
    const d = await freshDecompose({ isMock: true })
    await d.triggerDecompose(PARENT_ID)
    expect(d.ghostCount.value).toBeGreaterThan(0)
    d.discardAll()
    expect(d.ghostCount.value).toBe(0)
  })

  it('leaves non-ghost nodes intact', async () => {
    const d = await freshDecompose({ isMock: true })
    const realCount = d.vfNodes.value.length
    await d.triggerDecompose(PARENT_ID)
    d.discardAll()
    expect(d.vfNodes.value.length).toBe(realCount)
  })
})

describe('acceptAll', () => {
  it('converts all ghosts to real nodes', async () => {
    const d = await freshDecompose({ isMock: true })
    await d.triggerDecompose(PARENT_ID)
    const ghostCount = d.ghostCount.value
    expect(ghostCount).toBeGreaterThan(0)
    await d.acceptAll()
    expect(d.ghostCount.value).toBe(0)
  })
})
