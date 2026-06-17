/**
 * useChat — manages chat session state and AI communication.
 *
 * - Sends messages to POST /spaces/{spaceId}/ai/chat
 * - Calls applyMutations when the backend returns canvas mutations
 * - Tracks per-session ID for conversation memory
 */
import { ref } from 'vue'
import { useApi, ApiError } from './useApi'
import { useModelSelector } from './useModelSelector'
import type { AIChatResponse, GraphMutationAction } from '@/types/graph'
import type { ApplyResult } from './useMutationApplier'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  /** Human-readable summary of canvas mutations, e.g. "AI created 3 nodes" */
  mutationBadge?: string
  /** Raw mutations from the AI, for preview/apply-all */
  mutations?: GraphMutationAction[]
  /** Whether mutations have been applied */
  mutationsApplied?: boolean
  timestamp: Date
}

export function useChat(
  spaceId: string,
  applyMutations: (mutations: GraphMutationAction[]) => ApplyResult,
) {
  const api = useApi()
  const { selectedProvider, localModel } = useModelSelector()

  const messages = ref<ChatMessage[]>([])
  const isLoading = ref(false)
  const sessionId = ref<string | null>(null)
  const error = ref<string | null>(null)

  function _id() {
    return `${Date.now()}-${Math.random().toString(36).slice(2)}`
  }

  async function sendMessage(text: string): Promise<void> {
    const trimmed = text.trim()
    if (!trimmed || isLoading.value) return

    messages.value.push({
      id: _id(),
      role: 'user',
      content: trimmed,
      timestamp: new Date(),
    })

    isLoading.value = true
    error.value = null

    try {
      const body: Record<string, unknown> = {
        message: trimmed,
        provider: selectedProvider.value,
      }
      if (sessionId.value) body.session_id = sessionId.value
      if (selectedProvider.value === 'local' && localModel.value) {
        body.local_model = localModel.value
      }

      const resp = await api.post<AIChatResponse>(
        `/spaces/${spaceId}/ai/chat`,
        body,
      )

      // Persist session ID so history accumulates server-side
      if (resp.session_id) sessionId.value = resp.session_id

      // Apply canvas mutations and get summary badge
      let mutationBadge: string | undefined
      let pendingMutations: GraphMutationAction[] | undefined
      if (resp.mutations && resp.mutations.length > 0) {
        pendingMutations = resp.mutations
        // Auto-apply mutations immediately for status updates (fast feedback)
        const statusMutations = resp.mutations.filter(m => m.action === 'update_node')
        const otherMutations = resp.mutations.filter(m => m.action !== 'update_node')

        if (statusMutations.length > 0) {
          const result = applyMutations(statusMutations)
          if (result.summary) mutationBadge = result.summary
        }

        if (otherMutations.length > 0) {
          // Non-status mutations get a preview badge
          const counts = countMutations(otherMutations)
          mutationBadge = mutationBadge
            ? `${mutationBadge} · ${counts}`
            : counts
        }
      }

      messages.value.push({
        id: _id(),
        role: 'assistant',
        content: resp.reply,
        mutationBadge,
        mutations: pendingMutations,
        mutationsApplied: !pendingMutations || pendingMutations.every(m => m.action === 'update_node'),
        timestamp: new Date(),
      })
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? `Error ${err.status}: ${err.message}`
          : 'Failed to reach the AI. Check your connection.'
      error.value = msg
      messages.value.push({
        id: _id(),
        role: 'system',
        content: `⚠️ ${msg}`,
        timestamp: new Date(),
      })
    } finally {
      isLoading.value = false
    }
  }

  function clearChat(): void {
    messages.value = []
    sessionId.value = null
    error.value = null
  }

  function countMutations(mutations: GraphMutationAction[]): string {
    const counts: Record<string, number> = {}
    for (const m of mutations) {
      const key = m.action.replace('add_', '').replace('update_', '').replace('delete_', '')
      counts[key] = (counts[key] || 0) + 1
    }
    return Object.entries(counts)
      .map(([k, v]) => `${v} ${k}${v > 1 ? 's' : ''}`)
      .join(', ')
  }

  function applyPendingMutations(messageId: string): ApplyResult | null {
    const msg = messages.value.find(m => m.id === messageId)
    if (!msg || !msg.mutations || msg.mutationsApplied) return null
    const result = applyMutations(msg.mutations)
    msg.mutationsApplied = true
    msg.mutationBadge = result.summary || msg.mutationBadge
    return result
  }

  return { messages, isLoading, sessionId, error, sendMessage, clearChat, applyPendingMutations }
}
