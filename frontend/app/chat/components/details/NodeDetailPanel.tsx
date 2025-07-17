import React from 'react';
import { Node } from 'reactflow';
import { observer } from 'mobx-react-lite';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';

interface NodeDetailPanelProps {
  // runId 不再需要
  selectedNode: Node | null;
  onClose: () => void;
}

export const NodeDetailPanel = observer(({ selectedNode, onClose }: NodeDetailPanelProps) => {
  if (!selectedNode) {
    return null; // Should be controlled by parent
  }

  return (
    <div className="flex flex-col h-full p-2 border-l bg-white">
      <Card className="mb-2">
        <CardHeader className="p-2 flex flex-row items-center justify-between">
          <CardTitle className="text-base">Node Details</CardTitle>
          <Button variant="ghost" size="icon" className="h-6 w-6" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </CardHeader>
        <CardContent className="p-2 text-xs">
          <pre className="bg-gray-100 p-2 rounded overflow-auto max-h-48">
            {JSON.stringify(selectedNode.data, null, 2)}
          </pre>
        </CardContent>
      </Card>
      <h3 className="text-base font-semibold p-2">Activity Stream</h3>
    </div>
  );
});
NodeDetailPanel.displayName = 'NodeDetailPanel';
