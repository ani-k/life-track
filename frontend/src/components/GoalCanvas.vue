<script setup lang="ts">
import { ref, provide, onMounted, markRaw, computed } from 'vue'
import {
  VueFlow, useVueFlow,
  type NodeDragEvent, type NodeMouseEvent, type Connection,
} from '@vue-flow/core'
import { Background, BackgroundVariant } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'

import { useGraph } from '@/composables/useGraph'
import { useDecompose } from '@/composables/useDecompose'
import { useModelSelector } from '@/composables/useModelSelector'
import { useMutationApplier } from '@/composables/useMutationApplier'
import type { NodeCreate, NodeStatus, Provider } from '@/types/graph'
import GoalNode from './GoalNode.vue'
import GhostNode from './GhostNode.vue'
import ChatSidebar from './ChatSidebar.vue'
import NodeEditor from './NodeEditor.vue'
import TemplatePicker from './TemplatePicker.vue'
import UndoToast from './UndoToast.vue'
import SmartEdge from './SmartEdge.vue'
import SpaceSelector from './SpaceSelector.vue'
import CreateSpaceModal from './CreateSpaceModal.vue'
import ToastManager from './ToastManager.vue'

// ── Props ──────────────────────────────────────────────────────────────
const props = defineProps<{ spaceId: string }>()

const emit = defineEmits<{
  switchSpace: [spaceId: string]
}>()

// ── Node types ─────────────────────────────────────────────────────────
const nodeTypes = {
  goalNode:  markRaw(GoalNode) as any,
  ghostNode: markRaw(GhostNode) as any,
}

// ── Edge types ─────────────────────────────────────────────────────────
const edgeTypes = {
  smartEdge: markRaw(SmartEdge) as any,
}

// ── Graph state ────────────────────────────────────────────────────────
const {
  vfNodes, vfEdges,
  isLoading, error, isMock,
  selectedNode, selectNode,
  loadGraph, createNode, patchNodePosition, patchNodeStatus, updateNode, deleteNode,
} = useGraph(props.spaceId)

// ── Model selector ─────────────────────────────────────────────────────
const { selectedProvider, localModel, modelLabel } = useModelSelector()
const showModelDropdown = ref(false)
const editingLocalModel = ref(false)

// ── Decompose state ────────────────────────────────────────────────────
const {
  isDecomposing, decompositionError, ghostCount,
  triggerDecompose, acceptProposal, discardProposal, acceptAll, discardAll,
} = useDecompose(props.spaceId, vfNodes as any, vfEdges as any, isMock, selectedProvider, localModel)

// ── Mutation applier + chat sidebar ────────────────────────────────────
const { applyMutations } = useMutationApplier(vfNodes as any, vfEdges as any, props.spaceId)
const showChat = ref(false)

// ── Provide actions to child nodes ─────────────────────────────────────
export interface GraphActions {
  patchNodeStatus: (nodeId: string, status: NodeStatus) => Promise<void>
  triggerDecompose: (nodeId: string) => Promise<void>
  deleteNode: (nodeId: string) => Promise<void>
}
export interface DecomposeActions {
  acceptProposal: (ghostId: string) => Promise<void>
  discardProposal: (ghostId: string) => void
}

provide<GraphActions>('graphActions', { patchNodeStatus, triggerDecompose, deleteNode: handleDeleteNode })
provide<DecomposeActions>('decomposeActions', { acceptProposal, discardProposal })

// ── Vue Flow instance ──────────────────────────────────────────────────
const { screenToFlowCoordinate, fitView } = useVueFlow()

// ── Add node modal ─────────────────────────────────────────────────────
const showAddModal    = ref(false)
const isAdding        = ref(false)
const canvasRef       = ref<HTMLElement | null>(null)
const initialAddData  = ref<Partial<import('@/types/graph').GoalNode>>({})

// ── Edit node modal ────────────────────────────────────────────────────
const showEditModal   = ref(false)
const editingNodeId   = ref<string | null>(null)
const editingNodeData = computed(() => {
  if (!editingNodeId.value) return undefined
  const node = (vfNodes.value as any[]).find((n: any) => n.id === editingNodeId.value)
  return node?.data
})

// ── Template picker ────────────────────────────────────────────────────
const showTemplatePicker = ref(false)
const canvasIsEmpty = computed(() => 
  (vfNodes.value as any[]).filter((n: any) => n.type !== 'ghostNode').length === 0
)

// Show template picker when canvas is empty and not loading
const shouldShowTemplatePicker = computed(() => 
  canvasIsEmpty.value && !isLoading.value && showTemplatePicker.value
)

async function handleTemplateSelected(templateKey: string | null) {
  if (templateKey === null) {
    // Start from scratch - just hide the picker
    showTemplatePicker.value = false
  } else {
    // Template was loaded, reload the graph
    await loadGraph()
    showTemplatePicker.value = false
  }
}

// ── Undo system ────────────────────────────────────────────────────────
interface UndoState {
  type: 'delete'
  nodeId: string
  nodeTitle: string
}

const showUndo = ref(false)
const undoState = ref<UndoState | null>(null)

async function handleDeleteNode(nodeId: string) {
  const node = (vfNodes.value as any[]).find((n: any) => n.id === nodeId)
  if (!node) return
  
  undoState.value = {
    type: 'delete',
    nodeId: nodeId,
    nodeTitle: node.data?.title ?? 'node',
  }
  
  try {
    await deleteNode(nodeId, true) // soft delete
    showUndo.value = true
  } catch (err) {
    console.error('Failed to delete node:', err)
  }
}

async function handleUndo() {
  if (!undoState.value || undoState.value.type !== 'delete') return
  
  // For soft-deleted nodes, we can restore by reloading
  // (In a full implementation, you'd call a restore endpoint)
  await loadGraph()
  showUndo.value = false
  undoState.value = null
}

function handleCloseUndo() {
  showUndo.value = false
  undoState.value = null
}

// ── Space management ───────────────────────────────────────────────────
const showCreateSpaceModal = ref(false)
const toastManager = ref<InstanceType<typeof ToastManager> | null>(null)

function handleSwitchSpace(spaceId: string) {
  emit('switchSpace', spaceId)
}

function handleSpaceDeleted(deletedSpaceId: string) {
  // If we deleted the active space, switch to another remaining space
  if (deletedSpaceId === props.spaceId) {
    // We signal parent App.vue which needs to select a new space or reload spaces list
    // We can emit a special event or just wait for the page to select the first one
    emit('switchSpace', '')
  }
}

function handleOpenCreateSpace() {
  showCreateSpaceModal.value = true
}

function handleNotify(payload: { type: 'success' | 'error'; message: string }) {
  toastManager.value?.addToast(payload.type, payload.message)
}

async function handleSpaceCreated(spaceId: string) {
  showCreateSpaceModal.value = false
  emit('switchSpace', spaceId)
}

// ── Lifecycle ──────────────────────────────────────────────────────────
onMounted(async () => {
  await loadGraph()
  // Show template picker if canvas is empty after load
  if (canvasIsEmpty.value) {
    showTemplatePicker.value = true
  }
  setTimeout(() => fitView({ padding: 0.2, duration: 600 }), 100)
})

// ── Canvas event handlers ──────────────────────────────────────────────

function onNodeDragStop({ node }: NodeDragEvent) {
  if (node.type === 'ghostNode') return   // never persist ghost positions
  patchNodePosition(node.id, node.position)
}

function onNodeClick({ node }: NodeMouseEvent) {
  if (node.type === 'ghostNode') return
  // Open editor on click
  editingNodeId.value = node.id
  showEditModal.value = true
}

function onPaneClick() {
  selectNode(null)
  showModelDropdown.value = false
}

function onConnect(connection: Connection) {
  if (!connection.source || !connection.target) return
  vfEdges.value = [
    ...(vfEdges.value as any[]),
    {
      id: `e-${Date.now()}`,
      source: connection.source,
      target: connection.target,
      type: 'smoothstep',
      style: { stroke: '#84855c', strokeWidth: 2 },
    },
  ] as any
}

// ── Model selector ─────────────────────────────────────────────────────

function selectProvider(p: Provider) {
  selectedProvider.value = p
  editingLocalModel.value = false
  showModelDropdown.value = false
}

// ── Add node ───────────────────────────────────────────────────────────

function openAddModal() {
  initialAddData.value = {
    title: '',
    node_type: 'task',
    priority: 'medium',
    status: 'pending',
    tags: [],
    due_date: undefined,
    description: '',
  }
  showAddModal.value = true
}

async function handleSaveAdd(data: Partial<import('@/types/graph').GoalNode>) {
  if (isAdding.value) return
  isAdding.value = true
  try {
    const el = canvasRef.value
    const center = el
      ? screenToFlowCoordinate({
          x: el.getBoundingClientRect().left + el.clientWidth  / 2,
          y: el.getBoundingClientRect().top  + el.clientHeight / 2,
        })
      : { x: 200 + Math.random() * 200, y: 200 + Math.random() * 200 }

    // Cast the saved fields as NodeCreate to build correctly
    const nodePayload: NodeCreate = {
      title: data.title ?? '',
      node_type: data.node_type ?? 'task',
      status: data.status ?? 'pending',
      priority: data.priority ?? 'medium',
      tags: data.tags ?? [],
      description: data.description ?? undefined,
      due_date: data.due_date ?? undefined,
    }

    await createNode(nodePayload, center)
    showAddModal.value = false
  } finally {
    isAdding.value = false
  }
}

// ── Edit node ──────────────────────────────────────────────────────────

async function handleSaveEdit(data: Partial<import('@/types/graph').GoalNode>) {
  if (!editingNodeId.value) return
  await updateNode(editingNodeId.value, data)
  showEditModal.value = false
  editingNodeId.value = null
}

function handleCloseEdit() {
  showEditModal.value = false
  editingNodeId.value = null
}

// ── Smart Edge: Insert node ───────────────────────────────────────────
export interface SmartEdgeActions {
  insertNodeBetween: (sourceId: string, targetId: string, position: { x: number; y: number }) => Promise<void>
}

async function insertNodeBetween(_sourceId: string, _targetId: string, position: { x: number; y: number }) {
  const newNode = await createNode(
    { title: 'New Node', node_type: 'task' },
    { x: position.x - 100, y: position.y - 50 },
  )

  if (!newNode) return

  // TODO: Update edges - remove old edge and create two new edges
  // This requires backend support for edge CRUD
  // For now, the new node is created but edges need manual reconnection
}

provide<SmartEdgeActions>('smartEdgeActions', { insertNodeBetween })
</script>

<template>
  <div ref="canvasRef" class="relative w-full h-full bg-olive-50">

    <!-- ── Loading overlay ──────────────────────────────────────── -->
    <Transition name="fade">
      <div v-if="isLoading"
           class="absolute inset-0 z-50 flex items-center justify-center bg-olive-50/80 backdrop-blur-sm">
        <div class="flex flex-col items-center gap-3">
          <div class="w-8 h-8 border-4 border-olive-300 border-t-olive-600 rounded-full animate-spin" />
          <p class="text-sm text-olive-600 font-medium">Loading your canvas…</p>
        </div>
      </div>
    </Transition>

    <!-- ── Error banner ─────────────────────────────────────────── -->
    <div v-if="error || decompositionError"
         class="absolute top-16 left-1/2 -translate-x-1/2 z-40 bg-red-50 border border-red-200
                text-red-700 rounded-lg px-4 py-2 text-sm shadow">
      ⚠ {{ error || decompositionError }}
    </div>

    <!-- ── Mock badge ────────────────────────────────────────────── -->
    <div v-if="isMock && !isLoading"
         class="absolute bottom-6 left-1/2 -translate-x-1/2 z-40 bg-amber-50 border border-amber-200
                text-amber-700 rounded-full px-3 py-1 text-xs font-medium shadow-sm pointer-events-none">
      📋 Demo data — backend offline
    </div>

    <!-- ── Ghost-nodes action banner ────────────────────────────── -->
    <Transition name="slide-down">
      <div v-if="ghostCount > 0"
           class="absolute top-14 inset-x-0 z-30 flex justify-center px-4 pointer-events-none">
        <div class="pointer-events-auto flex items-center gap-3 bg-amber-50 border border-amber-200
                    rounded-full px-4 py-1.5 shadow text-sm">
          <span class="text-amber-700 font-medium">
            ✨ {{ ghostCount }} AI suggestion{{ ghostCount === 1 ? '' : 's' }}
          </span>
          <button
            class="text-emerald-700 font-semibold hover:underline"
            @click="acceptAll"
          >Accept all</button>
          <span class="text-amber-200">|</span>
          <button
            class="text-red-500 font-semibold hover:underline"
            @click="discardAll"
          >Discard all</button>
        </div>
      </div>
    </Transition>

    <!-- ── Toolbar ──────────────────────────────────────────────── -->
    <header class="absolute top-0 left-0 right-0 z-30 flex items-center justify-between
                   px-4 py-2.5 bg-white/80 backdrop-blur-sm border-b border-olive-100">
      <!-- Brand + Space Selector -->
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <span class="text-lg">🎯</span>
          <span class="font-semibold text-olive-800 tracking-tight">LifeTrack</span>
        </div>
        
        <!-- Space Selector -->
        <SpaceSelector
          :current-space-id="spaceId"
          @switch-space="handleSwitchSpace"
          @create-space="handleOpenCreateSpace"
          @space-deleted="handleSpaceDeleted"
        />
      </div>

      <div class="flex items-center gap-2">
        <!-- Selected node chip -->
        <span v-if="selectedNode"
              class="hidden sm:inline-block max-w-[160px] truncate text-xs text-olive-500
                     bg-olive-100 rounded-full px-2.5 py-1 font-medium">
          ✓ {{ selectedNode.title }}
        </span>

        <!-- ── Model selector dropdown ───────────────────────── -->
        <div class="relative">
          <button
            class="btn-olive-outline text-xs gap-1"
            :title="`LLM provider: ${modelLabel}`"
            @click.stop="showModelDropdown = !showModelDropdown"
          >
            <span>{{ selectedProvider === 'cloud' ? '☁️' : '🖥️' }}</span>
            <span class="hidden sm:inline">{{ modelLabel }}</span>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12" fill="currentColor" class="w-3 h-3">
              <path d="M6 8L2 4h8L6 8z"/>
            </svg>
          </button>

          <Transition name="dropdown">
            <div v-if="showModelDropdown"
                 class="absolute right-0 top-full mt-1 w-52 bg-white border border-olive-200
                        rounded-xl shadow-lg overflow-hidden z-50"
                 @click.stop>
              <!-- Cloud option -->
              <button
                class="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm hover:bg-olive-50 transition-colors"
                :class="selectedProvider === 'cloud' ? 'bg-olive-50 font-semibold text-olive-900' : 'text-olive-700'"
                @click="selectProvider('cloud')"
              >
                <span class="text-base">☁️</span>
                <div class="text-left">
                  <div class="font-medium">Cloud</div>
                  <div class="text-xs text-olive-400">GPT-4o via OpenAI</div>
                </div>
                <svg v-if="selectedProvider === 'cloud'" xmlns="http://www.w3.org/2000/svg"
                     viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5 ml-auto text-olive-600">
                  <path fill-rule="evenodd"
                    d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
                    clip-rule="evenodd" />
                </svg>
              </button>

              <div class="border-t border-olive-100" />

              <!-- Local (Ollama) option -->
              <div
                class="px-3 py-2.5 cursor-pointer hover:bg-olive-50 transition-colors"
                :class="selectedProvider === 'local' ? 'bg-olive-50' : ''"
                @click="selectProvider('local')"
              >
                <div class="flex items-center gap-2.5">
                  <span class="text-base">🖥️</span>
                  <div class="flex-1 text-left">
                    <div class="text-sm font-medium" :class="selectedProvider === 'local' ? 'text-olive-900 font-semibold' : 'text-olive-700'">
                      Local (Ollama)
                    </div>
                    <div class="text-xs text-olive-400">localhost:11434</div>
                  </div>
                  <svg v-if="selectedProvider === 'local'" xmlns="http://www.w3.org/2000/svg"
                       viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5 text-olive-600 shrink-0">
                    <path fill-rule="evenodd"
                      d="M12.416 3.376a.75.75 0 0 1 .208 1.04l-5 7.5a.75.75 0 0 1-1.154.114l-3-3a.75.75 0 0 1 1.06-1.06l2.353 2.353 4.493-6.74a.75.75 0 0 1 1.04-.207Z"
                      clip-rule="evenodd" />
                  </svg>
                </div>
                <!-- Inline model name input -->
                <div v-if="selectedProvider === 'local'" class="mt-2" @click.stop>
                  <input
                    v-model="localModel"
                    type="text"
                    placeholder="gemma3:2b"
                    class="w-full text-xs rounded-md border border-olive-300 px-2 py-1
                           focus:outline-none focus:ring-1 focus:ring-olive-400"
                  />
                  <p class="text-[10px] text-olive-400 mt-0.5">Ollama model name</p>
                </div>
              </div>
            </div>
          </Transition>
        </div>

        <!-- AI Decompose button (needs selected node) -->
        <button
          class="btn-olive-outline"
          :disabled="!selectedNode || isDecomposing"
          :title="selectedNode ? `Decompose '${selectedNode.title}'` : 'Select a node first'"
          @click="selectedNode && triggerDecompose(selectedNode.id)"
        >
          <svg v-if="!isDecomposing" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"
               fill="currentColor" class="w-4 h-4">
            <path fill-rule="evenodd"
              d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171
                 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10
                 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637
                 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.83-4.4z"
              clip-rule="evenodd"
            />
          </svg>
          <div v-else class="w-4 h-4 border-2 border-olive-400 border-t-olive-700 rounded-full animate-spin" />
          <span class="hidden sm:inline">{{ isDecomposing ? 'Decomposing…' : 'AI Decompose' }}</span>
        </button>

        <!-- Add Node -->
        <button class="btn-olive" @click="openAddModal">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
            <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5z" />
          </svg>
          Add Node
        </button>

        <!-- Chat toggle -->
        <button
          class="btn-olive-outline"
          :class="{ 'bg-olive-100 border-olive-400': showChat }"
          @click="showChat = !showChat"
          title="AI Chat"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="w-4 h-4">
            <path d="M3.505 2.365A41.369 41.369 0 0 1 9 2c1.863 0 3.697.124 5.495.365 1.247.167 2.18 1.253 2.18 2.51v5.25c0 1.257-.933 2.343-2.18 2.51A41.257 41.257 0 0 1 9 12.75c-1.863 0-3.697-.124-5.495-.365-1.247-.167-2.18-1.253-2.18-2.51V4.875c0-1.257.933-2.343 2.18-2.51ZM18 14.25a.75.75 0 0 1 .75.75v.75a2.25 2.25 0 0 1-2.25 2.25H3.5a2.25 2.25 0 0 1-2.25-2.25V15a.75.75 0 0 1 1.5 0v.75a.75.75 0 0 0 .75.75h13a.75.75 0 0 0 .75-.75V15a.75.75 0 0 1 .75-.75Z" />
          </svg>
          <span class="hidden sm:inline">Chat</span>
        </button>
      </div>
    </header>

    <!-- ── Vue Flow Canvas ──────────────────────────────────────── -->
    <VueFlow
      v-model:nodes="vfNodes"
      v-model:edges="vfEdges"
      :node-types="nodeTypes"
      :edge-types="edgeTypes"
      :min-zoom="0.1"
      :max-zoom="4"
      fit-view-on-init
      elevate-nodes-on-select
      class="pt-[52px]"
      @node-drag-stop="onNodeDragStop"
      @node-click="onNodeClick"
      @pane-click="onPaneClick"
      @connect="onConnect"
    >
      <Background :variant="BackgroundVariant.Dots" :gap="24" :size="1.2" pattern-color="#b9ba88" />
      <Controls position="bottom-right" />
      <MiniMap
        position="bottom-left"
        :node-color="(n) => n.data?.canvas_data?.style?.color ?? '#84855c'"
        mask-color="rgba(245,245,239,0.85)"
      />
    </VueFlow>

    <!-- ── Add Node Modal ───────────────────────────────────────── -->
    <NodeEditor
      :is-open="showAddModal"
      mode="create"
      :initial-data="initialAddData"
      @save="handleSaveAdd"
      @close="showAddModal = false"
    />

    <!-- ── Node Editor Modal ────────────────────────────────────────── -->
    <NodeEditor
      :is-open="showEditModal"
      mode="edit"
      :initial-data="editingNodeData"
      @save="handleSaveEdit"
      @close="handleCloseEdit"
    />

    <!-- ── Template Picker (Empty State) ─────────────────────────────── -->
    <TemplatePicker
      v-if="shouldShowTemplatePicker"
      :space-id="spaceId"
      @template-selected="handleTemplateSelected"
    />

    <!-- ── Undo Toast ────────────────────────────────────────────── -->
    <UndoToast
      :show="showUndo"
      :message="`Deleted '${undoState?.nodeTitle || 'node'}'. `"
      @undo="handleUndo"
      @close="handleCloseUndo"
    />

    <!-- ── Chat Sidebar ─────────────────────────────────────────── -->
    <Transition name="slide-right">
      <div
        v-if="showChat"
        class="absolute top-0 right-0 z-40 h-full"
      >
        <ChatSidebar
          :space-id="spaceId"
          :apply-mutations="applyMutations"
          @close="showChat = false"
          @notify="handleNotify"
        />
      </div>
    </Transition>

    <!-- ── Create Space Modal ─────────────────────────────────────── -->
    <CreateSpaceModal
      :is-open="showCreateSpaceModal"
      @close="showCreateSpaceModal = false"
      @created="handleSpaceCreated"
    />

    <!-- ── Toast Notifications ─────────────────────────────────────── -->
    <ToastManager ref="toastManager" />

  </div>
</template>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.modal-enter-active, .modal-leave-active { transition: opacity 0.2s ease; }
.modal-enter-from, .modal-leave-to { opacity: 0; }

/* Increase handle hit area for easier edge connections */
:deep(.vue-flow__handle) {
  width: 16px !important;
  height: 16px !important;
  border-width: 2px !important;
}

:deep(.vue-flow__handle:hover) {
  width: 20px !important;
  height: 20px !important;
}

.dropdown-enter-active, .dropdown-leave-active { transition: opacity 0.15s ease, transform 0.15s ease; }
.dropdown-enter-from, .dropdown-leave-to { opacity: 0; transform: translateY(-4px); }

.slide-down-enter-active, .slide-down-leave-active { transition: opacity 0.2s ease, transform 0.2s ease; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; transform: translateY(-8px); }

.slide-right-enter-active, .slide-right-leave-active { transition: transform 0.25s ease; }
.slide-right-enter-from, .slide-right-leave-to { transform: translateX(100%); }
</style>
