<script setup lang="ts">
/**
 * GoalNode — custom Vue Flow node rendered as an olive card.
 *
 * Receives typed NodeProps from Vue Flow. Injects graphActions from
 * GoalCanvas (provide/inject) so it can trigger status updates without
 * prop-drilling or a global store.
 *
 * inheritAttrs: false — required because Vue Flow passes node-internal
 * attributes (position, dimensions, connectable, etc.) to the component.
 * With multiple root elements (fragment) Vue cannot auto-inherit them,
 * which would cause a console warning. We explicitly opt out.
 */
import { computed, inject } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { GoalNode, NodeStatus } from '@/types/graph'
import type { GraphActions } from './GoalCanvas.vue'
import { useHighlight } from '@/composables/useHighlight'

defineOptions({ inheritAttrs: false })

// ── Props (Vue Flow injects these for custom nodes) ────────────────────
const props = defineProps<{
  id: string
  data: GoalNode
  selected?: boolean
}>()

// ── Injected actions from GoalCanvas ──────────────────────────────────
const graphActions = inject<GraphActions>('graphActions')!

// ── Highlight state (module singleton) ────────────────────────────────
const { highlightedIds } = useHighlight()
const isHighlighted = computed(() => highlightedIds.value.has(props.id))

// ── Computed styling ───────────────────────────────────────────────────

const typeConfig = computed(() => {
  const map: Record<GoalNode['node_type'], { label: string; border: string; badge: string }> = {
    goal:          { label: 'Goal',       border: 'border-l-olive-700', badge: 'bg-olive-700 text-white' },
    milestone:     { label: 'Milestone',  border: 'border-l-olive-500', badge: 'bg-olive-500 text-white' },
    task:          { label: 'Task',       border: 'border-l-olive-300', badge: 'bg-olive-200 text-olive-800' },
    note:          { label: 'Note',       border: 'border-l-gray-300',  badge: 'bg-gray-100 text-gray-600' },
    ai_suggestion: { label: 'AI',         border: 'border-l-amber-400', badge: 'bg-amber-100 text-amber-800' },
  }
  return map[props.data.node_type]
})

const priorityDot = computed(() => {
  const map: Record<GoalNode['priority'], string> = {
    critical: 'bg-red-500',
    high:     'bg-orange-400',
    medium:   'bg-olive-400',
    low:      'bg-gray-300',
  }
  return map[props.data.priority]
})

const isCompleted = computed(() => props.data.status === 'completed')

const dueDateLabel = computed(() => {
  if (!props.data.due_date) return null
  return new Date(props.data.due_date).toLocaleDateString('en', { month: 'short', day: 'numeric' })
})

// ── Actions ────────────────────────────────────────────────────────────

function toggleStatus() {
  const next: NodeStatus = isCompleted.value ? 'pending' : 'completed'
  graphActions.patchNodeStatus(props.id, next)
}

function onDecompose(e: MouseEvent) {
  e.stopPropagation()
  graphActions.triggerDecompose(props.id)
}

function onDelete(e: MouseEvent) {
  e.stopPropagation()
  graphActions.deleteNode(props.id)
}
</script>

<template>
  <!-- Target handle (top) — receives incoming edges -->
  <Handle type="target" :position="Position.Top" />

  <div
    class="goal-node-card relative bg-white rounded-xl border border-olive-200 border-l-4 shadow-node
           transition-all duration-150 select-none overflow-hidden"
    :class="[
      typeConfig.border,
      selected ? 'shadow-node-selected ring-2 ring-olive-500' : '',
      isHighlighted ? 'ring-2 ring-olive-400 ring-offset-1 animate-pulse shadow-lg' : '',
    ]"
    style="min-width: 220px; max-width: 280px;"
  >
    <!-- ── Header row ─────────────────────────────────────────── -->
    <div class="flex items-center justify-between px-3 pt-2.5 pb-1 gap-2">
      <div class="flex items-center gap-1.5 min-w-0">
        <!-- Node type badge -->
        <span
          class="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide shrink-0"
          :class="typeConfig.badge"
        >
          {{ typeConfig.label }}
        </span>

        <!-- Icon from canvas_data -->
        <span v-if="data.canvas_data.style.icon" class="text-sm leading-none">
          {{ data.canvas_data.style.icon }}
        </span>
      </div>

      <!-- Actions: AI badge + priority dot + decompose button -->
      <div class="flex items-center gap-1.5 shrink-0">
        <!-- AI badge -->
        <span
          v-if="data.ai_provenance.ai_generated"
          class="inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-semibold
                 bg-amber-100 text-amber-700"
          :title="`AI-generated · ${data.ai_provenance.ai_model} · ${((data.ai_provenance.ai_confidence ?? 0) * 100).toFixed(0)}% confidence`"
        >
          ✨ AI
        </span>

        <!-- Priority dot -->
        <div
          class="w-2.5 h-2.5 rounded-full"
          :class="priorityDot"
          :title="`Priority: ${data.priority}`"
        />

        <!-- Decompose (magic wand) button — only for goal/milestone/task -->
        <button
          v-if="data.node_type !== 'note'"
          class="ml-0.5 rounded-md p-0.5 text-olive-400 hover:text-olive-700 hover:bg-olive-100
                 transition-colors duration-100"
          title="AI Decompose"
          @click="onDecompose"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
            <path fill-rule="evenodd"
              d="M8.694 2.295a.75.75 0 0 0-1.388 0l-1.3 3.127L2.9 5.773a.75.75 0 0 0-.416 1.302l2.574 2.21-.78 3.284a.75.75 0 0 0 1.107.808L8 11.53l2.614 1.847a.75.75 0 0 0 1.108-.808l-.78-3.284 2.573-2.21a.75.75 0 0 0-.415-1.302l-3.105-.35-1.3-3.128Z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
        
        <!-- Delete button -->
        <button
          class="ml-0.5 rounded-md p-0.5 text-gray-400 hover:text-red-600 hover:bg-red-50
                 transition-colors duration-100"
          title="Delete node"
          @click="onDelete"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
            <path fill-rule="evenodd"
              d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.3l.815 8.15A1.5 1.5 0 0 0 5.357 15h5.286a1.5 1.5 0 0 0 1.492-1.35l.815-8.15h.3a.75.75 0 0 0 0-1.5H11v-.75A2.25 2.25 0 0 0 8.75 1h-1.5A2.25 2.25 0 0 0 5 3.25Zm2.25-.75a.75.75 0 0 0-.75.75V4h3v-.75a.75.75 0 0 0-.75-.75h-1.5ZM6.05 6a.75.75 0 0 1 .787.713l.275 5.5a.75.75 0 0 1-1.498.075l-.275-5.5A.75.75 0 0 1 6.05 6Zm3.9 0a.75.75 0 0 1 .712.788l-.275 5.5a.75.75 0 0 1-1.498-.075l.275-5.5a.75.75 0 0 1 .786-.713Z"
              clip-rule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>

    <!-- ── Main content ───────────────────────────────────────── -->
    <div class="flex items-start gap-2 px-3 pb-2.5">
      <!-- Status checkbox -->
      <input
        type="checkbox"
        :checked="isCompleted"
        class="mt-0.5 h-4 w-4 rounded border-olive-300 text-olive-600 cursor-pointer shrink-0
               accent-olive-600 focus:ring-olive-500"
        :title="isCompleted ? 'Mark as pending' : 'Mark as completed'"
        @change.stop="toggleStatus"
      />

      <!-- Text content -->
      <div class="flex-1 min-w-0">
        <p
          class="text-sm font-medium text-olive-900 leading-snug break-words"
          :class="{ 'line-through text-olive-400': isCompleted }"
        >
          {{ data.title }}
        </p>
        <p
          v-if="data.description"
          class="mt-0.5 text-xs text-olive-500 leading-snug line-clamp-2 break-words"
        >
          {{ data.description }}
        </p>
      </div>
    </div>

    <!-- ── Footer: tags + due date ────────────────────────────── -->
    <div
      v-if="data.tags.length || dueDateLabel"
      class="flex items-center justify-between flex-wrap gap-x-2 gap-y-1 px-3 pb-2.5"
    >
      <div class="flex flex-wrap gap-1">
        <span
          v-for="tag in data.tags.slice(0, 3)"
          :key="tag"
          class="inline-block rounded-full px-1.5 py-0.5 text-[10px] bg-olive-100 text-olive-600"
        >
          #{{ tag }}
        </span>
        <span
          v-if="data.tags.length > 3"
          class="inline-block rounded-full px-1.5 py-0.5 text-[10px] bg-olive-100 text-olive-500"
        >
          +{{ data.tags.length - 3 }}
        </span>
      </div>
      <span v-if="dueDateLabel" class="text-[10px] text-olive-400 shrink-0">
        📅 {{ dueDateLabel }}
      </span>
    </div>
  </div>

  <!-- Source handle (bottom) — emits outgoing edges -->
  <Handle type="source" :position="Position.Bottom" />
</template>

