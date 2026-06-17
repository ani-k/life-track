<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import GoalCanvas from '@/components/GoalCanvas.vue'
import CreateSpaceModal from '@/components/CreateSpaceModal.vue'

/**
 * Root-level space management with URL hash-based routing.
 * This satisfies the "Navigation" requirement where the URL structure is tied to space_id.
 */
const activeSpaceId = ref<string | null>(null)
const isLoading = ref(true)
const isCreateModalOpen = ref(false)
const showHomeScreen = ref(false)
const spacesList = ref<any[]>([])

async function fetchSpaces() {
  try {
    const response = await fetch('/api/v1/spaces')
    if (!response.ok) throw new Error('Failed to fetch spaces')
    const spaces = await response.json()
    spacesList.value = spaces

    // Try raising correct space from location hash (e.g. #/space/<uuid> or #/<uuid>)
    const hash = window.location.hash
    if (hash && hash.startsWith('#/spaces/')) {
      const hashSpaceId = hash.replace('#/spaces/', '')
      const found = spaces.find((s: any) => s.id === hashSpaceId)
      if (found) {
        activeSpaceId.value = found.id
        showHomeScreen.value = false
        return
      }
    }

    // Default routing
    if (hash === '#/home' || spaces.length === 0) {
      showHomeScreen.value = true
      activeSpaceId.value = null
    } else if (spaces.length > 0) {
      activeSpaceId.value = spaces[0].id
      window.location.hash = `#/spaces/${spaces[0].id}`
      showHomeScreen.value = false
    } else {
      activeSpaceId.value = null
      showHomeScreen.value = true
    }
  } catch (err) {
    console.error('Error fetching spaces:', err)
  } finally {
    isLoading.value = false
  }
}

// Watch location hash changes
function handleHashChange() {
  const hash = window.location.hash
  if (hash === '#/home' || hash === '' || hash === '#/') {
    activeSpaceId.value = null
    showHomeScreen.value = true
    return
  }
  if (hash.startsWith('#/spaces/')) {
    const spaceId = hash.replace('#/spaces/', '')
    activeSpaceId.value = spaceId
    showHomeScreen.value = false
  }
}

onMounted(() => {
  fetchSpaces()
  window.addEventListener('hashchange', handleHashChange)
})

onUnmounted(() => {
  window.removeEventListener('hashchange', handleHashChange)
})

function onSwitchSpace(spaceId: string) {
  if (spaceId === '') {
    // If deleted space, reload spaces list
    fetchSpaces()
  } else if (spaceId === 'home') {
    activeSpaceId.value = null
    showHomeScreen.value = true
    window.location.hash = '#/home'
  } else {
    activeSpaceId.value = spaceId
    window.location.hash = `#/spaces/${spaceId}`
    showHomeScreen.value = false
  }
}

function handleSpaceCreated(spaceId: string) {
  activeSpaceId.value = spaceId
  window.location.hash = `#/spaces/${spaceId}`
  showHomeScreen.value = false
  fetchSpaces()
}

function selectSpace(spaceId: string) {
  activeSpaceId.value = spaceId
  window.location.hash = `#/spaces/${spaceId}`
  showHomeScreen.value = false
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
      v-else-if="activeSpaceId && !showHomeScreen"
      :key="activeSpaceId"
      :space-id="activeSpaceId"
      @switch-space="onSwitchSpace"
    />

    <!-- Home Screen / Empty list of spaces -->
    <div v-else class="flex flex-col items-center justify-center h-full p-6 overflow-y-auto">
      <div class="max-w-4xl w-full flex flex-col space-y-8 p-4">
        
        <!-- Header -->
        <div class="text-center space-y-3">
          <div class="inline-flex w-16 h-16 bg-olive-50 rounded-full items-center justify-center text-3xl shadow-inner animate-pulse">
            🎯
          </div>
          <h1 class="text-3xl font-extrabold text-olive-900 tracking-tight">LifeTrack Spaces</h1>
          <p class="text-gray-500 max-w-lg mx-auto text-sm leading-relaxed">
            Welcome to LifeTrack Spatial OS — change workspaces, load templates, and organize goals dynamically using a visual canvas and an integrated AI assistant.
          </p>
        </div>

        <!-- Spaces Grid -->
        <div v-if="spacesList.length > 0" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div
            v-for="space in spacesList"
            :key="space.id"
            class="group bg-white rounded-2xl border border-olive-100 shadow-md hover:shadow-xl transition-all duration-300 p-6 flex flex-col justify-between cursor-pointer transform hover:-translate-y-1"
            @click="selectSpace(space.id)"
          >
            <div class="space-y-3">
              <div class="flex items-center justify-between">
                <span class="text-2xl">📁</span>
                <span class="text-[10px] bg-olive-50 text-olive-700 px-2 py-1 rounded-full font-semibold uppercase tracking-wider">Active</span>
              </div>
              <div>
                <h3 class="text-lg font-bold text-gray-905 group-hover:text-olive-700 transition-colors">{{ space.name }}</h3>
                <p class="text-xs text-gray-400 line-clamp-2 mt-1">{{ space.description || 'No description provided.' }}</p>
              </div>
            </div>
            <div class="mt-4 pt-3 border-t border-gray-50 flex items-center justify-between text-xs text-gray-450">
              <span>View Canvas</span>
              <span class="text-olive-600 font-bold group-hover:translate-x-1.5 transition-transform duration-300 inline-block">→</span>
            </div>
          </div>

          <!-- Quick Actions Tile -->
          <div
            class="bg-olive-50/40 hover:bg-olive-50/80 rounded-2xl border-2 border-dashed border-olive-200 shadow-sm hover:shadow-md transition-all duration-300 p-6 flex flex-col items-center justify-center text-center cursor-pointer min-h-[160px] group"
            @click="isCreateModalOpen = true"
          >
            <span class="text-2xl text-olive-600 mb-2 group-hover:scale-110 transition-transform duration-200">➕</span>
            <span class="font-bold text-olive-800 text-sm">Create New Space</span>
            <p class="text-[11px] text-olive-600/70 mt-1 max-w-[180px]">Add another workspace to coordinate and structure your goals.</p>
          </div>
        </div>

        <!-- Absolutely Empty State -->
        <div v-else class="max-w-md w-full mx-auto bg-white rounded-2xl shadow-xl p-8 border border-olive-100 flex flex-col items-center text-center space-y-6">
          <div class="w-16 h-16 bg-olive-50 rounded-full flex items-center justify-center text-3xl shadow-inner animate-bounce">
            🎯
          </div>
          <div class="space-y-2">
            <h2 class="text-2xl font-bold text-olive-905">Welcome to LifeTrack!</h2>
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
    </div>

    <!-- Modal to create a new space -->
    <CreateSpaceModal
      :is-open="isCreateModalOpen"
      @close="isCreateModalOpen = false"
      @created="handleSpaceCreated"
    />
  </div>
</template>
