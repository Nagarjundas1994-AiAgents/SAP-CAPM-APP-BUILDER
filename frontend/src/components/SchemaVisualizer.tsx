'use client';

import React, { useMemo } from 'react';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

interface EntityField {
  name: string;
  type: string;
  isKey?: boolean;
}

interface EntityDefinition {
  name: string;
  fields: EntityField[];
}

interface SchemaVisualizerProps {
  entities: EntityDefinition[];
}

// A custom node for representing a CDS/OData entity
const EntityNode = ({ data }: { data: EntityDefinition }) => {
  return (
    <div className="bg-gray-900 border-2 border-blue-500 rounded-xl shadow-xl w-64 overflow-hidden">
      {/* Header */}
      <div className="bg-blue-600/20 px-4 py-2 border-b border-blue-500/30 flex items-center justify-between">
        <h3 className="font-bold text-white text-sm">{data.name}</h3>
      </div>
      
      {/* Fields */}
      <div className="p-2 space-y-1 bg-black/40">
        {data.fields.map((field, idx) => {
          // Identify foreign keys for basic styling (assuming they contain 'Id' or end with 'ID')
          const isForeignKey = field.name.toLowerCase().endsWith('id') && field.name !== 'ID';
          
          return (
            <div key={idx} className="flex items-center justify-between text-xs px-2 py-1 rounded hover:bg-white/5">
              <span className={`font-medium ${field.isKey ? 'text-blue-400' : isForeignKey ? 'text-purple-400' : 'text-gray-300'}`}>
                {field.isKey && '🔑 '}{field.name}
              </span>
              <span className="text-gray-500 font-mono text-[10px]">{field.type}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const nodeTypes = {
  entity: EntityNode,
};

export default function SchemaVisualizer({ entities }: SchemaVisualizerProps) {
  // Convert our simplified entity definitions into React Flow Nodes and Edges
  const { initialNodes, initialEdges } = useMemo(() => {
    const nodes: any[] = [];
    const edges: any[] = [];

    // Very basic auto-layout using a grid
    const cols = Math.ceil(Math.sqrt(entities.length));
    const xSpacing = 350;
    const ySpacing = 250;

    entities.forEach((entity, index) => {
      // Calculate position
      const row = Math.floor(index / cols);
      const col = index % cols;

      nodes.push({
        id: entity.name,
        type: 'entity',
        position: { x: col * xSpacing + 50, y: row * ySpacing + 50 },
        data: { ...entity },
      });

      // Infer edges/relationships based on field names ending with 'ID' (basic heuristic)
      entity.fields.forEach(field => {
        if (field.name.length > 2 && field.name.endsWith('ID') && field.name !== 'ID') {
          // E.g., CustomerID -> attempt to link to Customer entity
          const targetName = field.name.slice(0, -2); 
          const targetExists = entities.some(e => e.name.toLowerCase() === targetName.toLowerCase());
          
          if (targetExists) {
            // Find actual target name with correct case
            const actualTarget = entities.find(e => e.name.toLowerCase() === targetName.toLowerCase())?.name;
            if (actualTarget) {
               edges.push({
                id: `${entity.name}-${actualTarget}`,
                source: actualTarget, // usually 1 target
                target: entity.name,  // to N sources
                animated: true,
                style: { stroke: '#8b5cf6', strokeWidth: 2 },
                markerEnd: {
                  type: MarkerType.ArrowClosed,
                  color: '#8b5cf6',
                },
              });
            }
          }
        }
      });
    });

    return { initialNodes: nodes, initialEdges: edges };
  }, [entities]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Update nodes/edges if entities prop changes
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  return (
    <div className="w-full h-full min-h-[500px] border border-white/10 rounded-xl overflow-hidden bg-black/40">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        className="bg-zinc-900/50"
      >
        <Controls className="bg-white/5 border-white/10 fill-white" />
        <MiniMap 
          nodeColor={(n) => '#3b82f6'} 
          maskColor="rgba(0, 0, 0, 0.7)"
          className="bg-gray-900 border border-white/10 rounded-lg"
        />
        <Background color="#333" gap={16} />
      </ReactFlow>
    </div>
  );
}
