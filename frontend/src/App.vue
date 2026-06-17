<script setup lang="ts">
import { ref, onMounted } from 'vue'
import GoalCanvas from '@/components/GoalCanvas.vue'

/**
 * Root-level space management.
 *
 * Design note: no Vue Router yet.
 */
const activeSpaceId = ref<string | null>(null)
const isLoading = ref(true)

async function fetchSpaces() {
  try {
    const response = await fetch('/api/v1/spaces')
    if (!response.ok) throw new Error('Failed to fetch spaces')
    const spaces = await response.json()
    if (spaces.length > 0) {
      activeSpaceId.value = spaces[0].id
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
</script>

<template>
  <div class="w-full h-screen overflow-hidden">
    <div v-if="isLoading" class="flex items-center justify-center h-full">Loading...</div>
    <GoalCanvas
      v-else-if="activeSpaceId"
      :key="activeSpaceId"
      :space-id="activeSpaceId"
      @switch-space="onSwitchSpace"
    />
    <div v-else class="flex items-center justify-center h-full">No spaces found. Create one.</div>
  </div>
</template>
