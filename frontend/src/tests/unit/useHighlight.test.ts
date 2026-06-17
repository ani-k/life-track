/**
 * Tests for useHighlight composable.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Use fake timers so highlight timeout is controllable
describe('useHighlight', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.resetModules()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts with empty highlighted set', async () => {
    const { useHighlight } = await import('@/composables/useHighlight')
    const { highlightedIds } = useHighlight()
    expect(highlightedIds.value.size).toBe(0)
  })

  it('adds ids to highlighted set on highlight()', async () => {
    const { useHighlight } = await import('@/composables/useHighlight')
    const { highlightedIds, highlight } = useHighlight()
    highlight(['node-1', 'node-2'])
    expect(highlightedIds.value.has('node-1')).toBe(true)
    expect(highlightedIds.value.has('node-2')).toBe(true)
  })

  it('clears highlighted ids after duration', async () => {
    const { useHighlight } = await import('@/composables/useHighlight')
    const { highlightedIds, highlight } = useHighlight()
    highlight(['node-1'], 1000)
    expect(highlightedIds.value.has('node-1')).toBe(true)
    vi.advanceTimersByTime(1001)
    expect(highlightedIds.value.size).toBe(0)
  })

  it('does nothing for empty ids array', async () => {
    const { useHighlight } = await import('@/composables/useHighlight')
    const { highlightedIds, highlight } = useHighlight()
    highlight([])
    expect(highlightedIds.value.size).toBe(0)
  })

  it('replaces previous set on second highlight call', async () => {
    const { useHighlight } = await import('@/composables/useHighlight')
    const { highlightedIds, highlight } = useHighlight()
    highlight(['a'])
    highlight(['b', 'c'])
    expect(highlightedIds.value.has('a')).toBe(false)
    expect(highlightedIds.value.has('b')).toBe(true)
    expect(highlightedIds.value.has('c')).toBe(true)
  })
})
