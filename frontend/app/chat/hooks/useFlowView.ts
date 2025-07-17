import { useMemo, useState, useCallback } from 'react';
import { toJS } from 'mobx';
import { Node, Edge } from 'reactflow';
import { FlowViewModel, FlowNodeData, sessionStore } from '@/app/stores/sessionStore';
import { getLayoutedElements } from '../lib/flow-utils';

export function useFlowView(flowStructure: FlowViewModel | null): {
  nodes: Node<FlowNodeData>[];
  edges: Edge[];
  onNodeSizesChange: (nodeId: string, size: { width: number; height: number }) => void;
} {
  const [nodeSizes, setNodeSizes] = useState<Map<string, { width: number; height: number }>>(() => new Map());

  const onNodeSizesChange = useCallback((nodeId: string, size: { width: number; height: number }) => {
    setNodeSizes(prevSizes => {
      const newSizes = new Map(prevSizes);
      const currentSize = newSizes.get(nodeId);
      // Only update if the size has actually changed to prevent unnecessary re-renders
      if (!currentSize || currentSize.width !== size.width || currentSize.height !== size.height) {
        newSizes.set(nodeId, size);
        return newSizes;
      }
      return prevSizes;
    });
  }, []);

  const layoutResult = useMemo(() => {
    if (!flowStructure || !flowStructure.nodes) {
      return { nodes: [], edges: [] };
    }

    // Convert MobX observable to a plain JS object
    const plainFlowStructure = toJS(flowStructure);

    // The backend provides the basic structure, which conforms to Node<FlowNodeData>
    const nodesFromBackend: Node<FlowNodeData>[] = plainFlowStructure.nodes.map(n => ({
      ...n,
      position: { x: 0, y: 0 }, // Initial position, layout will override
    }));
    const edgesFromBackend = plainFlowStructure.edges;

    // Get streaming content map from sessionStore
    const streamingContentMap = sessionStore.streamingContent;

    // Calculate layout using the new utility function with streaming content
    return getLayoutedElements(nodesFromBackend, edgesFromBackend, nodeSizes, streamingContentMap);

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flowStructure, nodeSizes, sessionStore.streamingContent]);

  return { ...layoutResult, onNodeSizesChange };
}
