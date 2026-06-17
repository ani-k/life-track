<script setup lang="ts">
/**
 * SmartEdge.vue — Custom Vue Flow edge with '+' button on hover
 * to insert a node between source and target.
 */
import { computed, inject } from 'vue'
import { EdgeProps, BaseEdge, getSmoothStepPath } from '@vue-flow/core'
import type { SmartEdgeActions } from './GoalCanvas.vue'

const props = defineProps<EdgeProps>()

const smartEdgeActions = inject<SmartEdgeActions>('smartEdgeActions')

// Calculate path
const path = computed(() =>
  getSmoothStepPath({
    sourceX: props.sourceX,
    sourceY: props.sourceY,
    sourcePosition: props.sourcePosition,
    targetX: props.targetX,
    targetY: props.targetY,
    targetPosition: props.targetPosition,
  })
)

// Calculate midpoint for the '+' button
const midpoint = computed(() => ({
  x: (props.sourceX + props.targetX) / 2,
  y: (props.sourceY + props.targetY) / 2,
}))

function handleInsertNode() {
  smartEdgeActions?.insertNodeBetween(props.source, props.target, midpoint.value)
}
</script>

<template>
  <g class="smart-edge-group">
    <!-- Base edge path -->
    <BaseEdge
      :id="id"
      :path="path[0]"
      :marker-end="markerEnd"
      :style="{ stroke: '#9ca3af', strokeWidth: 2 }"
    />

    <!-- '+' button (visible on hover) -->
    <g
      class="insert-button opacity-0 group-hover:opacity-100 transition-opacity duration-200"
      :transform="`translate(${midpoint.x}, ${midpoint.y})`"
      @click.stop="handleInsertNode"
      style="cursor: pointer;"
    >
      <!-- Button background -->
      <circle
        r="12"
        fill="white"
        stroke="#6b7280"
        stroke-width="2"
        class="hover:fill-olive-50 hover:stroke-olive-600 transition-all"
      />
      <!-- Plus icon -->
      <line
        x1="-6"
        y1="0"
        x2="6"
        y2="0"
        stroke="#6b7280"
        stroke-width="2"
        stroke-linecap="round"
        class="hover:stroke-olive-600"
      />
      <line
        x1="0"
        y1="-6"
        x2="0"
        y2="6"
        stroke="#6b7280"
        stroke-width="2"
        stroke-linecap="round"
        class="hover:stroke-olive-600"
      />
    </g>
  </g>
</template>

<style scoped>
.smart-edge-group {
  pointer-events: all;
}

.smart-edge-group:hover .insert-button {
  opacity: 1;
}

.insert-button circle,
.insert-button line {
  transition: all 0.2s ease;
}

.insert-button:hover circle {
  fill: #f0fdf4;
  stroke: #65a30d;
}

.insert-button:hover line {
  stroke: #65a30d;
}
</style>
