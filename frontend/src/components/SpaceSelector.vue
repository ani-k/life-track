<script setup lang="ts">
/**
 * SpaceSelector.vue — Dropdown to switch between spaces
 * 
 * Shows current space and allows creating new ones.
 */
import { ref, computed, onMounted } from 'vue'
import { useApi } from '@/composables/useApi'

export interface Space {
  id: string
  name: string
  description?: string
}

const props = defineProps<{
  currentSpaceId: string
}>()

const emit = defineEmits<{
  switchSpace: [spaceId: string]
  createSpace: []
  spaceDeleted: [spaceId: string]
}>()

const spaces = ref<Space[]>([])
const isOpen = ref(false)
const isLoading = ref(false)
const api = useApi()

const isRenaming = ref<string | null>(null)
const renameValue = ref('')

const currentSpace = computed(() => 
  spaces.value.find(s => s.id === props.currentSpaceId)
)

onMounted(async () => {
  await loadSpaces()
})

async function loadSpaces() {
  isLoading.value = true
  try {
    const result = await api.get<Space[]>('/spaces')
    spaces.value = result
  } catch (err) {
    console.error('Failed to load spaces:', err)
  } finally {
    isLoading.value = false
  }
}

function selectSpace(spaceId: string) {
  if (isRenaming.value) return // Prevent switching space during renaming
  isOpen.value = false
  emit('switchSpace', spaceId)
}

function openCreateModal() {
  isOpen.value = false
  emit('createSpace')
}

function startRename(space: Space, event: Event) {
  event.stopPropagation()
  isRenaming.value = space.id
  renameValue.value = space.name
}

async function saveRename(spaceId: string, event?: Event) {
  if (event) event.stopPropagation()
  if (!renameValue.value.trim()) {
    isRenaming.value = null
    return
  }
  try {
    const updated = await api.patch<Space>(`/spaces/${spaceId}`, { name: renameValue.value.trim() })
    const idx = spaces.value.findIndex(s => s.id === spaceId)
    if (idx !== -1) {
      spaces.value[idx] = updated
    }
  } catch (err) {
    console.error('Failed to rename space:', err)
  } finally {
    isRenaming.value = null
  }
}

function cancelRename(event: Event) {
  event.stopPropagation()
  isRenaming.value = null
}

async function deleteSpace(spaceId: string, event: Event) {
  event.stopPropagation()
  if (!confirm('Are you sure you want to delete this space? All associated nodes and edges will be deleted.')) {
    return
  }
  try {
    await api.delete(`/spaces/${spaceId}`)
    spaces.value = spaces.value.filter(s => s.id !== spaceId)
    emit('spaceDeleted', spaceId)
  } catch (err) {
    console.error('Failed to delete space:', err)
  }
}
</script>

<template>
  <div class="relative">
    <!-- Trigger button -->
    <button
      class="flex items-center gap-2 px-3 py-2 bg-white border border-olive-200 rounded-lg
             hover:bg-olive-50 hover:border-olive-300 transition-colors shadow-sm"
      @click="isOpen = !isOpen"
    >
      <svg class="w-5 h-5 text-olive-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
              d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
      <span class="text-sm font-medium text-olive-800">
        {{ currentSpace?.name || 'Select Space' }}
      </span>
      <svg class="w-4 h-4 text-olive-500" :class="{ 'rotate-180': isOpen }" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
      </svg>
    </button>

    <!-- Dropdown menu -->
    <Transition name="dropdown">
      <div
        v-if="isOpen"
        class="absolute top-full left-0 mt-2 w-72 bg-white border border-olive-200 rounded-lg shadow-xl z-50
               max-h-96 overflow-y-auto"
        @click.stop
      >
        <!-- Loading state -->
        <div v-if="isLoading" class="p-4 text-center text-sm text-olive-600">
          Loading spaces...
        </div>

        <!-- Space list -->
        <div v-else class="py-2">
          <div
            v-for="space in spaces"
            :key="space.id"
            class="w-full px-4 py-2 hover:bg-olive-50 transition-colors
                   flex items-center justify-between gap-1 group"
            :class="{ 'bg-olive-100 font-semibold': space.id === currentSpaceId && !isRenaming }"
            @click="selectSpace(space.id)"
          >
            <!-- Normal mode -->
            <div v-if="isRenaming !== space.id" class="flex-1 min-w-0 pr-2">
              <div class="font-medium text-olive-900 truncate">{{ space.name }}</div>
              <div v-if="space.description" class="text-xs text-olive-600 mt-0.5 truncate">
                {{ space.description }}
              </div>
            </div>

            <!-- Rename Mode -->
            <div v-else class="flex-1 flex items-center gap-1" @click.stop>
              <input
                v-model="renameValue"
                type="text"
                class="flex-1 text-xs border border-olive-300 rounded px-1 py-0.5 outline-none focus:ring-1 focus:ring-olive-500 text-olive-900"
                @keydown.enter="saveRename(space.id)"
                @keydown.esc="cancelRename"
                maxlength="100"
              />
              <button
                class="text-emerald-600 hover:text-emerald-800 p-0.5"
                @click="saveRename(space.id)"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" />
                </svg>
              </button>
              <button
                class="text-red-500 hover:text-red-700 p-0.5"
                @click="cancelRename"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- Actions when NOT renaming -->
            <div v-if="isRenaming !== space.id" class="flex items-center gap-0.5 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
              <button
                class="p-1 text-gray-500 hover:text-olive-700 hover:bg-olive-50 rounded"
                title="Rename Space"
                @click="startRename(space, $event)"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                </svg>
              </button>
              <button
                class="p-1 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                title="Delete Space"
                @click="deleteSpace(space.id, $event)"
              >
                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>

            <!-- Checkmark for current space -->
            <svg
              v-if="space.id === currentSpaceId && isRenaming !== space.id"
              class="w-4 h-4 text-olive-600 shrink-0 ml-1 block group-hover:hidden"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path fill-rule="evenodd"
                    d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                    clip-rule="evenodd" />
            </svg>
          </div>
        </div>

        <!-- Divider -->
        <div class="border-t border-olive-200"></div>

        <!-- Create new space -->
        <button
          class="w-full px-4 py-3 text-left text-sm font-medium text-olive-700 hover:bg-olive-50
                 transition-colors flex items-center gap-2"
          @click="openCreateModal"
        >
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Create New Space
        </button>
      </div>
    </Transition>

    <!-- Backdrop to close dropdown -->
    <div
      v-if="isOpen"
      class="fixed inset-0 z-40"
      @click="isOpen = false"
    ></div>
  </div>
</template>

<style scoped>
.dropdown-enter-active,
.dropdown-leave-active {
  transition: all 0.2s ease;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
