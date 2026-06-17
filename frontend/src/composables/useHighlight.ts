/**
 * useHighlight — module-level singleton.
 * Any component can call highlight(ids) to pulse-highlight nodes on the canvas.
 * GoalNode.vue reads highlightedIds to add a ring animation class.
 */
import { ref, type Ref } from 'vue'

const highlightedIds: Ref<Set<string>> = ref(new Set<string>())

export function useHighlight() {
  /**
   * Temporarily highlight a set of node IDs.
   * @param ids   Node IDs to highlight.
   * @param duration  How long to highlight in ms (default 1500).
   */
  function highlight(ids: string[], duration = 1500): void {
    if (ids.length === 0) return
    highlightedIds.value = new Set(ids)
    setTimeout(() => {
      highlightedIds.value = new Set()
    }, duration)
  }

  return { highlightedIds, highlight }
}
