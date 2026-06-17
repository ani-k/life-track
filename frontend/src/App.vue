<script setup lang="ts">
import { ref, onMounted } from 'vue'
import GoalCanvas from '@/components/GoalCanvas.vue'
import CreateSpaceModal from '@/components/CreateSpaceModal.vue'

/**
 * Root-level space management.
 *
 * Design note: no Vue Router yet.
 */
const activeSpaceId = ref<string | null>(null)
const isLoading = ref(true)
const isCreateModalOpen = ref(false)

async function fetchSpaces() {
  try {
    const response = await fetch('/api/v1/spaces')
    if (!response.ok) throw new Error('Failed to fetch spaces')
    const spaces = await response.json()
    if (spaces.length > 0) {
      activeSpaceId.value = spaces[0].id
    } else {
      activeSpaceId.value = null
    }
  } catch (err) {
    console.error('Error fetching spaces:', err)
  } finally {
    isLoading.value = false
  }
}

onMounted(fetchSpaces)

function onSwitchSpace(spaceId: string) {
  if (spaceId === '') {
    // If deleted space, fetch spaces list again and choose the first available
    fetchSpaces()
  } else {
    activeSpaceId.value = spaceId
  }
}

function handleSpaceCreated(spaceId: string) {
  activeSpaceId.value = spaceId
}
</script>

<template>
  <div class="w-full h-screen overflow-hidden bg-olive-50/50">
    <!-- Loader -->
    <div v-if="isLoading" class="flex flex-col items-center justify-center h-full gap-4 text-olive-800">
      <div class="w-10 h-10 border-4 border-olive-200 border-t-olive-600 rounded-full animate-spin"></div>
      <p class="font-medium text-lg">Loading Spaces...</p>
    </div>

    <!-- Active Canvas -->
    <GoalCanvas
      v-else-if="activeSpaceId"
      :key="activeSpaceId"
      :space-id="activeSpaceId"
      @switch-space="onSwitchSpace"
    />

    <!-- No spaces empty state (with beautiful welcome card and action button) -->
    <div v-else class="flex items-center justify-center h-full p-6">
      <div class="max-w-md w-full bg-white rounded-2xl shadow-xl p-8 border border-olive-100 flex flex-col items-center text-center space-y-6">
        <div class="w-16 h-16 bg-olive-50 rounded-full flex items-center justify-center text-3xl shadow-inner animate-bounce">
          🎯
        </div>
        <div class="space-y-2">
          <h1 class="text-2xl font-bold text-olive-905">Welcome to LifeTrack!</h1>
          <p class="text-gray-500 text-sm leading-relaxed">
            Every journey begins with a single step. Create your very first spatial workspace (Space) to start visualizing and mapping out your life goals.
          </p>
        </div>
        <button
          type="button"
          class="w-full py-3 px-5 text-sm font-semibold text-white bg-olive-600 hover:bg-olive-700 active:bg-olive-800 rounded-xl transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2"
          @click="isCreateModalOpen = true"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" stroke="currentColor" viewBox="0 0 24 24" class="w-5 h-5" stroke-width="2.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          Create First Space
        </button>
      </div>
    </div>

    <!-- Modal to create a new space -->
    <CreateSpaceModal
      :is-open="isCreateModalOpen"
      @close="isCreateModalOpen = false"
      @created="handleSpaceCreated"
    />
  </div>
</template>
