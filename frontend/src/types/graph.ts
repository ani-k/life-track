/**
 * TypeScript types mirroring the backend Pydantic schemas.
 * Used by Vue Flow canvas and all frontend components.
 */

// ── Enums ────────────────────────────────────────────────────────────────────

export type NodeType = 'goal' | 'milestone' | 'task' | 'note' | 'ai_suggestion'
export type NodeStatus = 'pending' | 'in_progress' | 'completed' | 'archived'
export type NodePriority = 'low' | 'medium' | 'high' | 'critical'
export type EdgeType = 'parent_child' | 'dependency' | 'cross_space' | 'ai_suggested' | 'reference'

// ── Canvas sub-types ──────────────────────────────────────────────────────────

export interface Position {
  x: number
  y: number
}

export interface Dimensions {
  width: number
  height: number
}

export interface NodeStyle {
  color: string   // hex e.g. "#84855c"
  icon: string | null
}

export interface CanvasData {
  position: Position
  dimensions: Dimensions
  style: NodeStyle
  collapsed: boolean
}

export interface Viewport {
  x: number
  y: number
  zoom: number
}

// ── Node ─────────────────────────────────────────────────────────────────────

export interface AIProvenance {
  ai_generated: boolean
  ai_model: string | null
  ai_confidence: number | null  // 0.0 – 1.0
}

export interface GoalNode {
  id: string
  space_id: string
  title: string
  description: string | null
  node_type: NodeType
  status: NodeStatus
  priority: NodePriority
  tags: string[]
  due_date: string | null      // ISO 8601
  completed_at: string | null
  created_at: string
  updated_at: string
  canvas_data: CanvasData
  ai_provenance: AIProvenance
}

export interface NodeCreate {
  title: string
  description?: string | null
  node_type?: NodeType
  status?: NodeStatus
  priority?: NodePriority
  tags?: string[]
  due_date?: string | null
  canvas_data?: Partial<CanvasData>
}

export interface NodeUpdate extends Partial<NodeCreate> {}

// ── Edge ─────────────────────────────────────────────────────────────────────

export interface EdgeStyle {
  animated: boolean
  stroke: string
  stroke_width: number
  marker_end: string
}

export interface GoalEdge {
  id: string
  space_id: string
  source_id: string
  target_id: string
  target_space_id: string | null
  edge_type: EdgeType
  label: string | null
  style: EdgeStyle
  ai_generated: boolean
  created_at: string
  updated_at: string
}

export interface EdgeCreate {
  source_id: string
  target_id: string
  edge_type?: EdgeType
  label?: string | null
  style?: Partial<EdgeStyle>
  target_space_id?: string | null
}

// ── Space / Graph ─────────────────────────────────────────────────────────────

export interface Space {
  id: string
  user_id: string
  name: string
  description: string | null
  viewport: Viewport
  created_at: string
  updated_at: string
}

export interface GraphResponse {
  space: Space
  nodes: GoalNode[]
  edges: GoalEdge[]
}

// ── AI ────────────────────────────────────────────────────────────────────────

export type Provider = 'cloud' | 'local'

export interface SubNodeProposal {
  title: string
  description: string | null
  node_type: NodeType
  priority: NodePriority
  tags: string[]
  offset_x: number
  offset_y: number
}

export interface DecompositionResponse {
  parent_node_id: string
  sub_nodes: SubNodeProposal[]
  suggested_edge_type: EdgeType
  reasoning: string
}

export interface GraphMutationAction {
  action: 'add_node' | 'update_node' | 'delete_node' | 'add_edge' | 'delete_edge'
  payload: Record<string, unknown>
}

export interface AIChatResponse {
  session_id: string
  reply: string
  mutations: GraphMutationAction[]
  tokens_used: number
}

// ── Vue Flow adapter helpers ──────────────────────────────────────────────────

/** Convert a GoalNode to a Vue Flow Node (with our data payload). */
export interface VFNode {
  id: string
  type: NodeType
  position: Position
  data: GoalNode
  style?: Record<string, string>
}

/** Convert a GoalEdge to a Vue Flow Edge. */
export interface VFEdge {
  id: string
  source: string
  target: string
  type: string
  label?: string
  animated?: boolean
  data: GoalEdge
}
