/**
 * Tests for useChat composable.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { GraphMutationAction } from '@/types/graph'

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockApplyMutations = vi.fn().mockReturnValue({ summary: '', affectedIds: [] })

// Mock the module-level singleton useModelSelector
vi.mock('@/composables/useModelSelector', () => {
  const { ref } = require('vue')
  return {
    useModelSelector: () => ({
      selectedProvider: ref('cloud'),
      localModel: ref(''),
      modelLabel: ref('GPT-4o'),
    }),
  }
})

const mockPost = vi.fn()
vi.mock('@/composables/useApi', () => ({
  useApi: () => ({ post: mockPost }),
  ApiError: class ApiError extends Error {
    status: number
    constructor(message: string, status: number) {
      super(message)
      this.status = status
    }
  },
}))

describe('useChat', () => {
  beforeEach(() => {
    vi.resetModules()
    mockPost.mockReset()
    mockApplyMutations.mockReset().mockReturnValue({ summary: '', affectedIds: [] })
  })

  it('starts with empty messages', async () => {
    const { useChat } = await import('@/composables/useChat')
    const chat = useChat('space-1', mockApplyMutations)
    expect(chat.messages.value).toHaveLength(0)
  })

  it('adds user message before API call', async () => {
    const { useChat } = await import('@/composables/useChat')
    mockPost.mockResolvedValue({
      session_id: 'sid-1',
      reply: 'Hello back!',
      mutations: [],
      tokens_used: 5,
    })

    const chat = useChat('space-1', mockApplyMutations)
    const promise = chat.sendMessage('Hello!')
    // User message should appear immediately (before await)
    expect(chat.messages.value[0].role).toBe('user')
    expect(chat.messages.value[0].content).toBe('Hello!')
    await promise
  })

  it('appends assistant reply after API response', async () => {
    const { useChat } = await import('@/composables/useChat')
    mockPost.mockResolvedValue({
      session_id: 'sid-1',
      reply: 'Here is my response.',
      mutations: [],
      tokens_used: 10,
    })

    const chat = useChat('space-1', mockApplyMutations)
    await chat.sendMessage('What should I do?')

    expect(chat.messages.value).toHaveLength(2)
    expect(chat.messages.value[1].role).toBe('assistant')
    expect(chat.messages.value[1].content).toBe('Here is my response.')
  })

  it('persists session_id from response', async () => {
    const { useChat } = await import('@/composables/useChat')
    mockPost.mockResolvedValue({
      session_id: 'abc-123',
      reply: 'Got it.',
      mutations: [],
      tokens_used: 3,
    })

    const chat = useChat('space-1', mockApplyMutations)
    await chat.sendMessage('Hi')
    expect(chat.sessionId.value).toBe('abc-123')
  })

  it('calls applyMutations when mutations are returned', async () => {
    const { useChat } = await import('@/composables/useChat')
    const mutation: GraphMutationAction = {
      action: 'add_node',
      payload: { id: 'n1', title: 'Test' },
    }
    mockPost.mockResolvedValue({
      session_id: 'sid-2',
      reply: 'Created a node!',
      mutations: [mutation],
      tokens_used: 8,
    })
    mockApplyMutations.mockReturnValue({ summary: 'AI created 1 node', affectedIds: ['n1'] })

    const chat = useChat('space-1', mockApplyMutations)
    await chat.sendMessage('Create a node')

    expect(mockApplyMutations).toHaveBeenCalledWith([mutation])
    const assistantMsg = chat.messages.value[1]
    expect(assistantMsg.mutationBadge).toBe('AI created 1 node')
  })

  it('adds system error message on API failure', async () => {
    const { useChat, } = await import('@/composables/useChat')
    const { ApiError } = await import('@/composables/useApi')
    mockPost.mockRejectedValue(new ApiError('Bad request', 400))

    const chat = useChat('space-1', mockApplyMutations)
    await chat.sendMessage('Fail me')

    const errMsg = chat.messages.value.find((m) => m.role === 'system')
    expect(errMsg).toBeDefined()
    expect(errMsg!.content).toContain('Error 400')
  })

  it('ignores empty or whitespace-only messages', async () => {
    const { useChat } = await import('@/composables/useChat')
    const chat = useChat('space-1', mockApplyMutations)
    await chat.sendMessage('   ')
    expect(mockPost).not.toHaveBeenCalled()
    expect(chat.messages.value).toHaveLength(0)
  })

  it('clearChat resets messages and sessionId', async () => {
    const { useChat } = await import('@/composables/useChat')
    mockPost.mockResolvedValue({
      session_id: 'sid-3',
      reply: 'OK',
      mutations: [],
      tokens_used: 2,
    })

    const chat = useChat('space-1', mockApplyMutations)
    await chat.sendMessage('hello')
    expect(chat.messages.value.length).toBeGreaterThan(0)
    expect(chat.sessionId.value).toBeTruthy()

    chat.clearChat()
    expect(chat.messages.value).toHaveLength(0)
    expect(chat.sessionId.value).toBeNull()
  })

  it('sends session_id in subsequent requests', async () => {
    const { useChat } = await import('@/composables/useChat')
    mockPost.mockResolvedValue({
      session_id: 'persistent-sid',
      reply: 'Reply',
      mutations: [],
      tokens_used: 1,
    })

    const chat = useChat('space-1', mockApplyMutations)
    await chat.sendMessage('First message')
    await chat.sendMessage('Second message')

    // Second call should include session_id
    const secondCallBody = mockPost.mock.calls[1][1] as Record<string, unknown>
    expect(secondCallBody.session_id).toBe('persistent-sid')
  })

  it('does not send while already loading', async () => {
    const { useChat } = await import('@/composables/useChat')
    let resolveFirst!: (v: unknown) => void
    mockPost.mockReturnValueOnce(
      new Promise((res) => { resolveFirst = res })
    )

    const chat = useChat('space-1', mockApplyMutations)
    // Don't await — let it stay in loading state
    chat.sendMessage('First')
    // Try sending a second message while loading
    await chat.sendMessage('Second while loading')

    // Only one API call should have been made
    expect(mockPost).toHaveBeenCalledTimes(1)
    resolveFirst({ session_id: 'sid', reply: 'Done', mutations: [], tokens_used: 1 })
  })
})
