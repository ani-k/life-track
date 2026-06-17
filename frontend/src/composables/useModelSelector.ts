/**
 * useModelSelector — shared singleton state for the selected LLM provider.
 *
 * Module-level refs: all components read the same reactive state without
 * needing a global store. Import { selectedProvider, localModel } anywhere.
 */
import { ref, computed } from 'vue'
import type { Provider } from '@/types/graph'

// Module-level singletons (shared across all component instances)
export const selectedProvider = ref<Provider>('cloud')
export const localModel = ref<string>('gemma3:2b')

export const modelLabel = computed(() =>
  selectedProvider.value === 'cloud'
    ? 'Cloud (GPT-4o)'
    : `Local (${localModel.value})`
)

export function useModelSelector() {
  return { selectedProvider, localModel, modelLabel }
}
