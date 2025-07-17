import React, { useState } from 'react';
import { KanbanView } from './KanbanView';
import { TimelineView } from './TimelineView';
import { observer } from 'mobx-react-lite';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
  } from "@/components/ui/select";

interface OutputPanelProps {
  runId: string;
}

export const OutputPanel = observer(({
  runId,
}: OutputPanelProps) => {
  const [groupMode, setGroupMode] = useState<'task' | 'agent'>('task');

  return (
    <div className="flex-1 overflow-hidden">
      <div className="relative h-full w-full px-3 pb-3 overflow-hidden">
          <div className="absolute top-4 right-6 z-10 rounded-lg bg-white flex items-center gap-2">
            <span className="text-sm text-gray-500">Group by:</span>
            <Select
              value={groupMode}
              onValueChange={(value: 'task' | 'agent') => setGroupMode(value)}
            >
              <SelectTrigger className="w-14 h-auto p-0 border-none bg-transparent text-sm text-gray-500 hover:text-gray-700 focus:ring-0 shadow-none">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="task">Status</SelectItem>
                <SelectItem value="agent">Agent</SelectItem>
              </SelectContent>
            </Select>
          </div>
        
          <div className="w-full h-full bg-white rounded-lg border border-[#E4E4E4] p-4 pt-16 overflow-y-auto">
            {/* Add a min-height container for the Kanban view to ensure its visual proportion */}
            <div className="min-h-[400px]">
              <KanbanView runId={runId} groupMode={groupMode} />
            </div>
            
            {/* Timeline Area */}
            <div className="border-t pt-6 mt-8">
              <h3 className="text-lg font-semibold mb-4">Execution Timeline</h3>
              <TimelineView />
            </div>
          </div>
      </div>
    </div>
  );
});
OutputPanel.displayName = "OutputPanel";
