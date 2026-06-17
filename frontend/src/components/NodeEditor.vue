<script setup lang="ts">
/**
 * NodeEditor.vue — Modal dialog for creating/editing nodes.
 * 
 * Features:
 * - Full form with all node fields (title, description, priority, tags, status, due_date)
 * - Create mode (no id) vs Edit mode (with id)
 * - Validation (e.g., title required)
 * - Keyboard shortcuts (Cmd+Enter to save, Esc to cancel)
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import type { GoalNode, NodeStatus, NodePriority, NodeType } from '@/types/graph'

// ── Props & Emits ──────────────────────────────────────────────────────────
const props = defineProps<{
  isOpen: boolean
  mode: 'create' | 'edit'
  initialData?: Partial<GoalNode>
}>()

const emit = defineEmits<{
  close: []
  save: [data: Partial<GoalNode>]
}>()

// ── Form State ─────────────────────────────────────────────────────────────
const form = ref({
  title: '',
  description: '',
  node_type: 'task' as NodeType,
  priority: 'medium' as NodePriority,
  status: 'pending' as NodeStatus,
  tags: [] as string[],
  due_date: null as string | null,
})

const tagInput = ref('')
const titleInput = ref<HTMLInputElement>()

// ── Validation ─────────────────────────────────────────────────────────────
const isTitleValid = computed(() => form.value.title.trim().length > 0)
const canSave = computed(() => isTitleValid.value)

// ── Watch for initial data ─────────────────────────────────────────────────
watch(
  () => [props.isOpen, props.initialData],
  () => {
    if (props.isOpen) {
      // Reset or populate form based on mode
      if (props.mode === 'edit' && props.initialData) {
        form.value = {
          title: props.initialData.title || '',
          description: props.initialData.description || '',
          node_type: props.initialData.node_type || 'task',
          priority: props.initialData.priority || 'medium',
          status: props.initialData.status || 'pending',
          tags: [...(props.initialData.tags || [])],
          due_date: props.initialData.due_date || null,
        }
      } else {
        // Create mode — reset form
        form.value = {
          title: props.initialData?.title || '',
          description: '',
          node_type: 'task',
          priority: 'medium',
          status: 'pending',
          tags: [],
          due_date: null,
        }
      }
      
      // Focus title input after dialog renders
      setTimeout(() => titleInput.value?.focus(), 100)
    }
  },
  { immediate: true }
)

// ── Tag Management ─────────────────────────────────────────────────────────
function addTag() {
  const tag = tagInput.value.trim()
  if (tag && !form.value.tags.includes(tag)) {
    form.value.tags.push(tag)
    tagInput.value = ''
  }
}

function removeTag(index: number) {
  form.value.tags.splice(index, 1)
}

function handleTagKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter') {
    e.preventDefault()
    addTag()
  }
}

// ── Actions ────────────────────────────────────────────────────────────────
function handleSave() {
  if (!canSave.value) return
  
  emit('save', {
    title: form.value.title.trim(),
    description: form.value.description.trim() || undefined,
    node_type: form.value.node_type,
    priority: form.value.priority,
    status: form.value.status,
    tags: form.value.tags,
    due_date: form.value.due_date || undefined,
  })
}

function handleClose() {
  emit('close')
}

// ── Keyboard Shortcuts ─────────────────────────────────────────────────────
function handleKeydown(e: KeyboardEvent) {
  if (!props.isOpen) return
  
  if (e.key === 'Escape') {
    handleClose()
  } else if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
    e.preventDefault()
    handleSave()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <!-- Backdrop overlay -->
  <Transition name="fade">
    <div
      v-if="isOpen"
      class="fixed inset-0 bg-black/50 z-40 flex items-center justify-center p-4"
      @click="handleClose"
    >
      <!-- Dialog -->
      <div
        class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-auto"
        @click.stop
      >
        <!-- Header -->
        <div class="sticky top-0 bg-white border-b border-olive-200 px-6 py-4 flex items-center justify-between">
          <h2 class="text-xl font-semibold text-olive-900">
            {{ mode === 'create' ? 'Create Node' : 'Edit Node' }}
          </h2>
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600 transition-colors"
            @click="handleClose"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Form -->
        <form class="p-6 space-y-6" @submit.prevent="handleSave">
          <!-- Title -->
          <div>
            <label for="node-title" class="block text-sm font-medium text-gray-700 mb-1">
              Title <span class="text-red-500">*</span>
            </label>
            <input
              id="node-title"
              ref="titleInput"
              v-model="form.title"
              type="text"
              required
              placeholder="E.g., Complete project proposal"
              class="w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-olive-400 focus:border-olive-400 outline-none transition"
              :class="{ 'border-red-300': !isTitleValid && form.title.length > 0 }"
            />
            <p v-if="!isTitleValid && form.title.length > 0" class="mt-1 text-sm text-red-600">
              Title is required
            </p>
          </div>

          <!-- Description -->
          <div>
            <label for="node-description" class="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              id="node-description"
              v-model="form.description"
              rows="3"
              placeholder="Add more details about this node..."
              class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-400 focus:border-olive-400 outline-none resize-none transition"
            />
          </div>

          <!-- Node Type & Priority (inline) -->
          <div class="grid grid-cols-2 gap-4">
            <!-- Node Type -->
            <div>
              <label for="node-type" class="block text-sm font-medium text-gray-700 mb-1">
                Type
              </label>
              <select
                id="node-type"
                v-model="form.node_type"
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-400 focus:border-olive-400 outline-none transition"
              >
                <option value="goal">Goal</option>
                <option value="milestone">Milestone</option>
                <option value="task">Task</option>
                <option value="note">Note</option>
              </select>
            </div>

            <!-- Priority -->
            <div>
              <label for="node-priority" class="block text-sm font-medium text-gray-700 mb-1">
                Priority
              </label>
              <select
                id="node-priority"
                v-model="form.priority"
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-400 focus:border-olive-400 outline-none transition"
              >
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>
            </div>
          </div>

          <!-- Status & Due Date (inline) -->
          <div class="grid grid-cols-2 gap-4">
            <!-- Status -->
            <div>
              <label for="node-status" class="block text-sm font-medium text-gray-700 mb-1">
                Status
              </label>
              <select
                id="node-status"
                v-model="form.status"
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-400 focus:border-olive-400 outline-none transition"
              >
                <option value="pending">Pending</option>
                <option value="in_progress">In Progress</option>
                <option value="completed">Completed</option>
                <option value="archived">Archived</option>
              </select>
            </div>

            <!-- Due Date -->
            <div>
              <label for="node-due-date" class="block text-sm font-medium text-gray-700 mb-1">
                Due Date
              </label>
              <input
                id="node-due-date"
                v-model="form.due_date"
                type="date"
                class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-400 focus:border-olive-400 outline-none transition"
              />
            </div>
          </div>

          <!-- Tags -->
          <div>
            <label for="node-tags" class="block text-sm font-medium text-gray-700 mb-1">
              Tags
            </label>
            <div class="flex flex-wrap gap-2 mb-2">
              <span
                v-for="(tag, index) in form.tags"
                :key="index"
                class="inline-flex items-center gap-1 px-3 py-1 bg-olive-100 text-olive-700 text-sm rounded-full"
              >
                {{ tag }}
                <button
                  type="button"
                  class="hover:text-olive-900 transition-colors"
                  @click="removeTag(index)"
                >
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </span>
            </div>
            <div class="flex gap-2">
              <input
                id="node-tags"
                v-model="tagInput"
                type="text"
                placeholder="Add a tag and press Enter"
                class="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-olive-400 focus:border-olive-400 outline-none transition"
                @keydown="handleTagKeydown"
              />
              <button
                type="button"
                class="px-4 py-2 bg-olive-100 text-olive-700 rounded-lg hover:bg-olive-200 transition-colors font-medium"
                @click="addTag"
              >
                Add
              </button>
            </div>
          </div>

          <!-- Footer Actions -->
          <div class="flex items-center justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              class="px-6 py-2 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors font-medium"
              @click="handleClose"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="px-6 py-2 bg-olive-600 text-white rounded-lg hover:bg-olive-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors font-medium"
              :disabled="!canSave"
            >
              {{ mode === 'create' ? 'Create' : 'Save' }}
            </button>
          </div>

          <!-- Keyboard hint -->
          <p class="text-xs text-gray-500 text-center">
            Press <kbd class="px-1.5 py-0.5 bg-gray-100 rounded text-gray-700">Esc</kbd> to cancel,
            <kbd class="px-1.5 py-0.5 bg-gray-100 rounded text-gray-700">⌘/Ctrl+Enter</kbd> to save
          </p>
        </form>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
