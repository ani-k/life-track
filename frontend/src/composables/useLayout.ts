import dagre from 'dagre'

export interface SimpleNode {
  id: string
  width?: number
  height?: number
  x?: number
  y?: number
}

export interface SimpleEdge {
  source: string
  target: string
}

/**
 * Perform a hierarchical tree layout using Dagre.
 * Modifies and returns nodes with calculated x and y positions.
 */
export function layoutTree(
  nodes: SimpleNode[],
  edges: SimpleEdge[],
  direction: 'TB' | 'LR' = 'TB' // TB: Top-to-Bottom, LR: Left-to-Right
): { id: string; x: number; y: number }[] {
  const g = new dagre.graphlib.Graph()
  
  // Set an object for all layout options:
  // - rankdir: direction for rank nodes. TB = top-to-bottom, LR = left-to-right
  // - nodesep: horizontal separation between adjacent nodes in the same rank
  // - ranksep: vertical separation between ranks
  g.setGraph({
    rankdir: direction,
    nodesep: 100,
    ranksep: 180,
    marginx: 50,
    marginy: 50,
  })

  // Default to assigning a new object as a label for each edge
  g.setDefaultEdgeLabel(() => ({}))

  // 1. Add nodes to layout
  nodes.forEach(node => {
    g.setNode(node.id, {
      width: node.width ?? 220,
      height: node.height ?? 80,
    })
  })

  // 2. Add edges to layout
  edges.forEach(edge => {
    // Only add edge if both endpoints exist in our layout node set
    if (nodes.some(n => n.id === edge.source) && nodes.some(n => n.id === edge.target)) {
      g.setEdge(edge.source, edge.target)
    }
  })

  // 3. Calculate Layout
  dagre.layout(g)

  // 4. Extract computed coordinates
  return nodes.map(node => {
    const computed = g.node(node.id)
    return {
      id: node.id,
      x: computed.x - (node.width ?? 220) / 2, // convert from center-based to top-left Vue Flow coordinate space
      y: computed.y - (node.height ?? 80) / 2,
    }
  })
}
