<template>
  <!-- Slide-over sidebar — 360 px wide, full viewport height -->
  <aside
    class="flex flex-col w-[360px] h-full bg-zinc-900 border-l border-zinc-700 shadow-2xl"
    aria-label="AI Chat"
  >
    <!-- Header -->
    <header class="flex items-center justify-between px-4 py-3 border-b border-zinc-700 shrink-0">
      <div class="flex items-center gap-2">
        <span class="text-olive-400 text-lg">🤖</span>
        <h2 class="text-sm font-semibold text-zinc-100">AI Assistant</h2>
      </div>
      <div class="flex items-center gap-2">
        <button
          title="Clear chat"
          class="text-xs text-zinc-400 hover:text-zinc-100 transition-colors px-2 py-1 rounded hover:bg-zinc-700"
          @click="chat.clearChat()"
        >
          Clear
        </button>
        <button
          title="Close chat"
          class="text-zinc-400 hover:text-zinc-100 transition-colors"
          @click="emit('close')"
        >
          ✕
        </button>
      </div>
    </header>

    <!-- Message list -->
    <div ref="scrollContainer" class="flex-1 overflow-y-auto px-3 py-4 space-y-3">
      <!-- Empty state -->
      <div v-if="chat.messages.value.length === 0" class="text-center text-zinc-500 text-sm mt-8 p-4">
        <p class="text-3xl mb-3">💬</p>
        <p class="text-zinc-300 font-semibold mb-2 text-base">I can create nodes, connect ideas, and update statuses.</p>
        <p class="text-xs text-zinc-400">Ask me anything about your goals or suggest changes to your canvas.</p>
      </div>

      <!-- Messages -->
      <div
        v-for="msg in chat.messages.value"
        :key="msg.id"
        :class="[
          'flex flex-col gap-1',
          msg.role === 'user' ? 'items-end' : 'items-start',
        ]"
      >
        <!-- Bubble -->
        <div
          :class="[
            'max-w-[290px] px-3 py-2 rounded-xl text-sm leading-relaxed break-words',
            msg.role === 'user'
              ? 'bg-olive-600 text-white rounded-br-sm'
              : msg.role === 'system'
                ? 'bg-red-900/60 text-red-300 rounded-bl-sm'
                : 'bg-zinc-700 text-zinc-100 rounded-bl-sm',
          ]"
        >
          <!-- Render assistant markdown; user/system as plain text -->
          <div
            v-if="msg.role === 'assistant'"
            class="prose prose-invert prose-sm max-w-none"
            v-html="renderMarkdown(msg.content)"
          />
          <span v-else>{{ msg.content }}</span>
        </div>

        <!-- Mutation badge -->
        <span
          v-if="msg.mutationBadge"
          class="text-[10px] px-2 py-0.5 rounded-full bg-olive-800 text-olive-300 font-medium"
        >
          ✨ {{ msg.mutationBadge }}
        </span>

        <!-- Action Preview: show pending mutations with Apply All button -->
        <div
          v-if="msg.mutations && msg.mutations.length > 0 && !msg.mutationsApplied"
          class="flex flex-col gap-1.5 mt-1 w-full max-w-[290px]"
        >
          <div class="text-[10px] text-zinc-400 font-medium px-1">Pending actions:</div>
          <div
            v-for="(m, mi) in msg.mutations.filter(m => m.action !== 'update_node')"
            :key="mi"
            class="flex items-center gap-1.5 text-[11px] bg-zinc-800 rounded-lg px-2 py-1.5 text-zinc-300"
          >
            <span class="shrink-0">{{ mutationIcon(m.action) }}</span>
            <span class="truncate">{{ mutationLabel(m) }}</span>
          </div>
          <button
            class="mt-1 text-xs font-medium text-olive-400 hover:text-olive-300
                   bg-olive-900/30 hover:bg-olive-900/50 rounded-lg px-3 py-1.5
                   transition-colors text-left"
            @click="handleApplyAll(msg.id)"
          >
            ✓ Apply all
          </button>
        </div>

        <!-- Timestamp -->
        <span class="text-[10px] text-zinc-600 px-1">
          {{ formatTime(msg.timestamp) }}
        </span>
      </div>

      <!-- Typing indicator -->
      <div v-if="chat.isLoading.value" class="flex items-start gap-1 px-1">
        <div class="flex gap-1 bg-zinc-700 px-3 py-2 rounded-xl rounded-bl-sm">
          <span v-for="i in 3" :key="i" class="w-1.5 h-1.5 bg-olive-400 rounded-full animate-bounce" :style="{ animationDelay: `${(i - 1) * 0.15}s` }" />
        </div>
      </div>
    </div>

    <!-- Input area -->
    <footer class="shrink-0 border-t border-zinc-700 p-3">
      <div class="flex gap-2 items-end">
        <textarea
          ref="inputRef"
          v-model="inputText"
          rows="1"
          placeholder="Ask about your goals… (Shift+Enter for new line)"
          class="
            flex-1 resize-none bg-zinc-800 text-zinc-100 text-sm rounded-xl
            px-3 py-2 outline-none border border-zinc-700 focus:border-olive-500
            placeholder:text-zinc-500 max-h-36 overflow-y-auto transition-colors
          "
          @keydown.enter.exact.prevent="handleSend"
          @input="autoResize"
        />
        <button
          :disabled="!inputText.trim() || chat.isLoading.value"
          class="
            shrink-0 btn-olive px-3 py-2 rounded-xl text-sm font-medium
            disabled:opacity-40 disabled:cursor-not-allowed
          "
          @click="handleSend"
        >
          ➤
        </button>
      </div>
    </footer>
  </aside>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useChat } from '@/composables/useChat'
import type { GraphMutationAction } from '@/types/graph'
import type { ApplyResult } from '@/composables/useMutationApplier'

// ── Props / Emits ─────────────────────────────────────────────────────────────

const props = defineProps<{
  spaceId: string
  applyMutations: (mutations: GraphMutationAction[]) => ApplyResult
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'notify', payload: { type: 'success' | 'error'; message: string }): void
}>()

// ── Chat state ────────────────────────────────────────────────────────────────

const chat = useChat(props.spaceId, props.applyMutations)

// ── DOM refs ──────────────────────────────────────────────────────────────────

const scrollContainer = ref<HTMLElement | null>(null)
const inputRef = ref<HTMLTextAreaElement | null>(null)
const inputText = ref('')

// ── Auto-scroll to bottom on new messages ─────────────────────────────────────

watch(
  () => chat.messages.value.length,
  async () => {
    await nextTick()
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight
    }
  },
)

// ── Textarea auto-resize ──────────────────────────────────────────────────────

function autoResize(e: Event) {
  const el = e.target as HTMLTextAreaElement
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

// ── Send message ──────────────────────────────────────────────────────────────

async function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  if (inputRef.value) {
    inputRef.value.style.height = 'auto'
  }
  await chat.sendMessage(text)
}

// ── Markdown rendering (sanitised) ────────────────────────────────────────────

function renderMarkdown(raw: string): string {
  const html = marked.parse(raw, { async: false }) as string
  // DOMPurify is only available in browser context; safe to call
  return typeof DOMPurify !== 'undefined' ? DOMPurify.sanitize(html) : html
}

// ── Timestamp ────────────────────────────────────────────────────────────────

function formatTime(d: Date): string {
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// ── Action Preview helpers ────────────────────────────────────────────────────

function mutationIcon(action: string): string {
  switch (action) {
    case 'add_node': return '➕'
    case 'add_edge': return '🔗'
    case 'delete_node': return '🗑️'
    case 'delete_edge': return '✂️'
    case 'update_node': return '✏️'
    default: return '⚡'
  }
}

function mutationLabel(m: import('@/types/graph').GraphMutationAction): string {
  const p = m.payload as Record<string, unknown>
  switch (m.action) {
    case 'add_node':
      return `Create "${p.title || 'untitled'}" (${p.node_type || 'task'})`
    case 'add_edge':
      return `Connect ${String(p.source_id || '?').slice(0, 8)}… → ${String(p.target_id || '?').slice(0, 8)}…`
    case 'update_node':
      return `Update ${String(p.id || '?').slice(0, 8)}… → ${String(p.status || 'changed')}`
    case 'delete_node':
      return `Delete node ${String(p.id || '?').slice(0, 8)}…`
    case 'delete_edge':
      return `Delete edge ${String(p.id || '?').slice(0, 8)}…`
    default:
      return `${m.action}`
  }
}

function handleApplyAll(messageId: string) {
  const result = chat.applyPendingMutations(messageId)
  if (result) {
    emit('notify', { type: 'success', message: result.summary || 'Changes applied' })
  }
}
</script>
