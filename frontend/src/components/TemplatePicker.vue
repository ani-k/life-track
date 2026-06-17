<script setup lang="ts">
/**
 * TemplatePicker.vue — Shows templates when a space is empty.
 * 
 * Features:
 * - Displays available templates (Health, Career, Personal)
 * - Shows template preview (node count, description)
 * - "Start from Scratch" option
 * - Creates space from template via API
 */
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'

const props = defineProps<{
  spaceId: string
}>()

const emit = defineEmits<{
  templateSelected: [templateKey: string | null]
}>()

const api = useApi()
const isLoading = ref(false)
const error = ref<string | null>(null)

interface Template {
  key: string
  name: string
  description: string
  icon: string
  nodeCount: number
  color: string
}

const templates: Template[] = [
  {
    key: 'health',
    name: 'Health',
    description: 'Track medical checkups, fitness goals, and nutrition',
    icon: '🏥',
    nodeCount: 4,
    color: 'bg-green-50 border-green-200 hover:bg-green-100',
  },
  {
    key: 'career',
    name: 'Career',
    description: 'Plan career milestones and professional development',
    icon: '💼',
    nodeCount: 4,
    color: 'bg-blue-50 border-blue-200 hover:bg-blue-100',
  },
  {
    key: 'personal',
    name: 'Personal',
    description: 'Manage hobbies, learning, and personal projects',
    icon: '🎯',
    nodeCount: 4,
    color: 'bg-purple-50 border-purple-200 hover:bg-purple-100',
  },
]

async function selectTemplate(templateKey: string | null) {
  if (templateKey === null) {
    // Start from scratch - just emit and let parent handle
    emit('templateSelected', null)
    return
  }

  isLoading.value = true
  error.value = null

  try {
    // Call API to seed space from template
    await api.post(`/templates/seed/${templateKey}`, { space_id: props.spaceId })
    emit('templateSelected', templateKey)
  } catch (err: any) {
    error.value = err.message || 'Failed to load template'
    console.error('[TemplatePicker] Error loading template:', err)
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="absolute inset-0 flex items-center justify-center bg-olive-50/95 backdrop-blur-sm z-30">
    <div class="max-w-4xl w-full p-8">
      <!-- Header -->
      <div class="text-center mb-8">
        <h2 class="text-3xl font-bold text-olive-900 mb-2">
          Welcome to Your Canvas
        </h2>
        <p class="text-olive-600">
          Choose a template to get started, or create your own
        </p>
      </div>

      <!-- Error message -->
      <div
        v-if="error"
        class="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm"
      >
        {{ error }}
      </div>

      <!-- Loading overlay -->
      <div
        v-if="isLoading"
        class="absolute inset-0 flex items-center justify-center bg-white/80 rounded-2xl"
      >
        <div class="flex flex-col items-center gap-3">
          <div class="w-8 h-8 border-4 border-olive-300 border-t-olive-600 rounded-full animate-spin" />
          <p class="text-sm text-olive-600 font-medium">Setting up your canvas…</p>
        </div>
      </div>

      <!-- Templates grid -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <button
          v-for="template in templates"
          :key="template.key"
          type="button"
          class="relative p-6 rounded-xl border-2 transition-all duration-200 text-left"
          :class="template.color"
          @click="selectTemplate(template.key)"
        >
          <div class="text-4xl mb-3">{{ template.icon }}</div>
          <h3 class="text-xl font-semibold text-gray-900 mb-2">
            {{ template.name }}
          </h3>
          <p class="text-sm text-gray-600 mb-4">
            {{ template.description }}
          </p>
          <div class="text-xs text-gray-500">
            {{ template.nodeCount }} nodes included
          </div>
        </button>
      </div>

      <!-- Start from scratch -->
      <div class="text-center">
        <button
          type="button"
          class="px-6 py-3 text-olive-700 hover:text-olive-900 font-medium transition-colors underline"
          @click="selectTemplate(null)"
        >
          Start from Scratch
        </button>
      </div>
    </div>
  </div>
</template>
