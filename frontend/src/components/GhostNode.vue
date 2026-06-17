<script setup lang="ts">
/**
 * GhostNode — AI-proposed sub-task rendered at 50% opacity.
 *
 * Shown after decompose until the user accepts or discards.
 * Injects `decomposeActions` from GoalCanvas for accept/discard callbacks.
 *
 * inheritAttrs: false — Vue Flow passes internal node props (position,
 * dimensions, connectable, etc.) that can't auto-inherit on fragment roots.
 */
import { inject } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { GhostNodeData } from '@/composables/useDecompose'
import type { DecomposeActions } from './GoalCanvas.vue'

defineOptions({ inheritAttrs: false })

defineProps<{
  id: string
  data: GhostNodeData
}>()

const decomposeActions = inject<DecomposeActions>('decomposeActions')!

const typeColors: Record<string, string> = {
  goal:      'border-l-olive-700',
  milestone: 'border-l-olive-500',
  task:      'border-l-olive-300',
  note:      'border-l-gray-300',
}
</script>

<template>
  <Handle type="target" :position="Position.Top" />

  <!-- 50% opacity wrapper — the "ghost" effect -->
  <div class="opacity-50 hover:opacity-80 transition-opacity duration-200">
    <div
      class="relative bg-white/90 rounded-xl border border-dashed border-olive-400 border-l-4
             shadow-node select-none overflow-hidden"
      :class="typeColors[data.proposal.node_type] ?? 'border-l-olive-300'"
       style="width: 260px;"
    >
      <!-- AI badge header -->
      <div class="flex items-center justify-between px-3 pt-2 pb-1 gap-2">
        <div class="flex items-center gap-1.5">
          <span class="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold
                       bg-amber-100 text-amber-700 uppercase tracking-wide">
            ✨ AI Suggestion
          </span>
          <span class="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-medium
                       bg-olive-100 text-olive-600 capitalize">
            {{ data.proposal.node_type }}
          </span>
        </div>
        <span class="text-[10px] text-olive-400 capitalize">{{ data.proposal.priority }}</span>
      </div>

      <!-- Title + description -->
      <div class="px-3 pb-2">
        <p class="text-sm font-medium text-olive-900 leading-snug break-words">
          {{ data.proposal.title }}
        </p>
        <p
          v-if="data.proposal.description"
          class="mt-0.5 text-xs text-olive-500 leading-snug line-clamp-2"
        >
          {{ data.proposal.description }}
        </p>
        <div v-if="data.proposal.tags.length" class="mt-1.5 flex flex-wrap gap-1">
          <span
            v-for="tag in data.proposal.tags.slice(0, 3)"
            :key="tag"
            class="inline-block rounded-full px-1.5 py-0.5 text-[10px] bg-olive-100 text-olive-600"
          >
            #{{ tag }}
          </span>
        </div>
      </div>

      <!-- Accept / Discard row -->
      <div class="flex border-t border-olive-100">
        <button
          class="flex-1 flex items-center justify-center gap-1 py-1.5 text-xs font-semibold
                 text-emerald-700 hover:bg-emerald-50 transition-colors duration-100"
          title="Accept this suggestion"
          @click.stop="decomposeActions.acceptProposal(id)"
        >
          <!-- Checkmark icon -->
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
            <path fill-rule="evenodd"
              d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
              clip-rule="evenodd"
            />
          </svg>
          Accept
        </button>
        <div class="w-px bg-olive-100" />
        <button
          class="flex-1 flex items-center justify-center gap-1 py-1.5 text-xs font-semibold
                 text-red-500 hover:bg-red-50 transition-colors duration-100"
          title="Discard this suggestion"
          @click.stop="decomposeActions.discardProposal(id)"
        >
          <!-- X icon -->
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
            <path d="M5.28 4.22a.75.75 0 0 0-1.06 1.06L6.94 8l-2.72 2.72a.75.75 0 1 0 1.06 1.06L8 9.06l2.72 2.72a.75.75 0 1 0 1.06-1.06L9.06 8l2.72-2.72a.75.75 0 0 0-1.06-1.06L8 6.94 5.28 4.22Z" />
          </svg>
          Discard
        </button>
      </div>
    </div>
  </div>

  <Handle type="source" :position="Position.Bottom" />
</template>
