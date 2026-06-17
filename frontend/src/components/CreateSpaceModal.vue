<script setup lang="ts">
/**
 * CreateSpaceModal.vue — Modal for creating a new space
 */
import { ref, watch } from 'vue'
import { useApi } from '@/composables/useApi'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  close: []
  created: [spaceId: string]
}>()

const name = ref('')
const description = ref('')
const isCreating = ref(false)
const error = ref<string | null>(null)
const api = useApi()

watch(
  () => props.isOpen,
  (newVal) => {
    if (newVal) {
      // Reset form when opened
      name.value = ''
      description.value = ''
      error.value = null
      setTimeout(() => {
        document.getElementById('space-name')?.focus()
      }, 100)
    }
  }
)

async function handleSubmit() {
  if (!name.value.trim() || isCreating.value) return
  
  isCreating.value = true
  error.value = null
  
  try {
    const result = await api.post<{ id: string }>('/spaces', {
      name: name.value.trim(),
      description: description.value.trim() || undefined,
    })
    emit('created', result.id)
    emit('close')
  } catch (err: any) {
    error.value = err.message || 'Failed to create space'
  } finally {
    isCreating.value = false
  }
}

function handleClose() {
  if (!isCreating.value) {
    emit('close')
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    handleClose()
  } else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
    handleSubmit()
  }
}
</script>

<template>
  <Transition name="modal">
    <div
      v-if="isOpen"
      class="fixed inset-0 z-50 flex items-center justify-center p-4"
      @click.self="handleClose"
    >
      <!-- Backdrop -->
      <div class="absolute inset-0 bg-black/40 backdrop-blur-sm"></div>

      <!-- Modal content -->
      <div
        class="relative bg-white rounded-xl shadow-2xl max-w-md w-full p-6 space-y-4"
        @keydown="handleKeydown"
      >
        <!-- Header -->
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-bold text-gray-900">Create New Space</h2>
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
        <form class="space-y-4" @submit.prevent="handleSubmit">
          <!-- Name field -->
          <div>
            <label for="space-name" class="block text-sm font-medium text-gray-700 mb-1">
              Space Name <span class="text-red-500">*</span>
            </label>
            <input
              id="space-name"
              v-model="name"
              type="text"
              placeholder="e.g., Health Goals, Career Path"
              class="w-full px-3 py-2 border border-gray-300 rounded-lg
                     focus:ring-2 focus:ring-olive-500 focus:border-olive-500
                     transition-colors"
              maxlength="100"
              required
            />
          </div>

          <!-- Description field -->
          <div>
            <label for="space-description" class="block text-sm font-medium text-gray-700 mb-1">
              Description (optional)
            </label>
            <textarea
              id="space-description"
              v-model="description"
              rows="3"
              placeholder="Brief description of this space..."
              class="w-full px-3 py-2 border border-gray-300 rounded-lg resize-none
                     focus:ring-2 focus:ring-olive-500 focus:border-olive-500
                     transition-colors"
              maxlength="500"
            ></textarea>
          </div>

          <!-- Error message -->
          <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-3">
            <p class="text-sm text-red-700">{{ error }}</p>
          </div>

          <!-- Actions -->
          <div class="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              class="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
              :disabled="isCreating"
              @click="handleClose"
            >
              Cancel
            </button>
            <button
              type="submit"
              class="px-4 py-2 text-sm font-medium text-white bg-olive-600 hover:bg-olive-700
                     rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed
                     flex items-center gap-2"
              :disabled="!name.trim() || isCreating"
            >
              <span v-if="isCreating">Creating...</span>
              <span v-else>Create Space</span>
            </button>
          </div>

          <!-- Keyboard hint -->
          <p class="text-xs text-gray-500 text-center">
            <kbd class="px-1.5 py-0.5 bg-gray-100 rounded text-[10px]">⌘</kbd>
            +
            <kbd class="px-1.5 py-0.5 bg-gray-100 rounded text-[10px]">Enter</kbd>
            to submit
          </p>
        </form>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .relative,
.modal-leave-active .relative {
  transition: transform 0.2s ease;
}

.modal-enter-from .relative,
.modal-leave-to .relative {
  transform: scale(0.95);
}
</style>
