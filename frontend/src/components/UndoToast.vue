<script setup lang="ts">
/**
 * UndoToast.vue — Toast notification for undo actions.
 * 
 * Features:
 * - Shows briefly when destructive action occurs
 * - "Undo" button to revert
 * - Auto-dismisses after timeout
 */
import { ref, watch } from 'vue'

const props = defineProps<{
  show: boolean
  message: string
  timeout?: number
}>()

const emit = defineEmits<{
  undo: []
  close: []
}>()

const visible = ref(false)
let timeoutId: number | null = null

watch(
  () => props.show,
  (newVal) => {
    if (newVal) {
      visible.value = true
      // Auto-dismiss after timeout
      if (timeoutId) clearTimeout(timeoutId)
      timeoutId = window.setTimeout(() => {
        handleClose()
      }, props.timeout || 5000)
    } else {
      visible.value = false
    }
  }
)

function handleUndo() {
  if (timeoutId) clearTimeout(timeoutId)
  visible.value = false
  emit('undo')
}

function handleClose() {
  if (timeoutId) clearTimeout(timeoutId)
  visible.value = false
  emit('close')
}
</script>

<template>
  <Transition name="slide-up">
    <div
      v-if="visible"
      class="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50
             bg-gray-900 text-white px-6 py-4 rounded-lg shadow-2xl
             flex items-center gap-4 max-w-md"
    >
      <p class="flex-1 text-sm font-medium">
        {{ message }}
      </p>
      <button
        type="button"
        class="px-4 py-2 bg-white text-gray-900 rounded font-medium text-sm hover:bg-gray-100 transition-colors"
        @click="handleUndo"
      >
        Undo
      </button>
      <button
        type="button"
        class="text-gray-400 hover:text-white transition-colors"
        @click="handleClose"
      >
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s ease;
}

.slide-up-enter-from {
  opacity: 0;
  transform: translate(-50%, 20px);
}

.slide-up-leave-to {
  opacity: 0;
  transform: translate(-50%, 10px);
}
</style>
