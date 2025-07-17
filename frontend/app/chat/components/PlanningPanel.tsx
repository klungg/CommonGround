import React, { useState, useRef, useEffect } from 'react';
import { observer } from 'mobx-react-lite';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Circle, Plus, X, Check, Trash2, SquarePen, Star, Search, Dot } from "lucide-react";
import { sessionStore, EnrichedWorkModule } from '@/app/stores/sessionStore';

interface PlanningPanelProps {
  runId: string;
}

type EditingTask = {
  id: string;
  name: string;
  description: string;
} | {
  id: 'new';
  name: string;
  description: string;
};

export const PlanningPanel = observer(({ runId }: PlanningPanelProps) => {
  const [editingTask, setEditingTask] = useState<EditingTask | null>(null);
  const editingTextareaRef = useRef<HTMLTextAreaElement>(null);
  const prevEditingTaskRef = useRef<EditingTask | null>(null);

  const pendingTasks = sessionStore.kanbanViewModel?.view_by_status?.pending || [];

  useEffect(() => {
    // Only focus when editingTask changes from null to a value
    if (prevEditingTaskRef.current === null && editingTask && editingTextareaRef.current) {
      editingTextareaRef.current.focus();
    }
    // Update the reference to the previous value
    prevEditingTaskRef.current = editingTask;
  }, [editingTask]);

  const handleSave = () => {
    if (!editingTask) return;

    const action = editingTask.id === 'new'
      ? { action: 'add', details: { name: editingTask.name, description: editingTask.description } } as const
      : { action: 'update', details: { module_id: editingTask.id, name: editingTask.name, description: editingTask.description } } as const;
    
    sessionStore.manageWorkModulesRequest(runId, [action]);
    setEditingTask(null);
  };

  const handleDelete = (moduleId: string) => {
    sessionStore.manageWorkModulesRequest(runId, [{ action: 'delete', details: { module_id: moduleId } }]);
  };

  const handleAddTask = () => {
    setEditingTask({ id: 'new', name: 'New Task', description: '' });
  };

  const handleEditTask = (task: EnrichedWorkModule) => {
    setEditingTask({ id: task.module_id, name: task.name, description: task.description });
  };

  const renderTaskItem = (task: EnrichedWorkModule) => (
    <li key={task.module_id} className="group mb-2">
      <div className="relative flex items-start rounded-lg border border-[#E4E4E4] p-3 hover:bg-white">
        <div className="flex items-start gap-1 flex-1 min-w-0">
          <Dot className="h-4 w-4 flex-shrink-0 stroke-[4px] mt-1" />
          <span className="text-sm break-words font-medium">{task.name}</span>
        </div>
        <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity bg-white p-1 rounded-lg">
          <Button size="icon" variant="ghost" className="h-6 w-6 rounded-md" onClick={() => handleEditTask(task)}>
            <SquarePen className="h-4 w-4" />
          </Button>
          <Button size="icon" variant="ghost" className="h-6 w-6 rounded-md hover:text-red-500" onClick={() => handleDelete(task.module_id)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </li>
  );

  const renderEditingView = () => {
    if (!editingTask) return null;
    return (
      <li className="group mb-2">
        <div className="relative">
          <div className="border-2 border-black rounded-lg p-2 space-y-2">
            <Textarea
              placeholder="Task Name"
              value={editingTask.name}
              onChange={(e) => setEditingTask({ ...editingTask, name: e.target.value })}
              className="w-full border-0 px-1 py-1 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent resize-none text-sm font-medium"
              rows={1}
            />
            <Textarea
              ref={editingTextareaRef}
              placeholder="Task Description"
              value={editingTask.description}
              onChange={(e) => setEditingTask({ ...editingTask, description: e.target.value })}
              className="w-full border-0 px-1 py-1 focus-visible:ring-0 focus-visible:ring-offset-0 bg-transparent resize-none min-h-[60px] text-sm"
            />
          </div>
          <div className="h-8 relative">
            <div className="absolute right-0 top-2 flex gap-1">
              <Button size="icon" variant="outline" className="h-6 w-6" onClick={() => setEditingTask(null)}>
                <X className="h-4 w-4" />
              </Button>
              <Button size="icon" className="h-6 w-6 bg-black hover:bg-black/80" onClick={handleSave}>
                <Check className="h-4 w-4 text-white" />
              </Button>
            </div>
          </div>
        </div>
      </li>
    );
  };

  return (
    <div className="px-3 pb-3 flex-1 overflow-y-auto">
      <div className="flex gap-3 h-full">
        <div className="bg-white rounded-lg p-3 shadow-sm w-[320px] border border-[#E4E4E4]">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2 bg-[#F2F2F2] rounded-full px-2 py-1">
              <Circle className="h-3 w-3 text-gray-400 fill-current" />
              <span className="text-sm font-medium">Planning</span>
            </div>
          </div>
          
          <div className="mb-2">
            <Button variant="outline" className="w-full flex items-center gap-1 justify-start h-[40px] px-3" onClick={handleAddTask} disabled={!!editingTask}>
              <Plus className="h-5 w-5" />
              <span>New Task</span>
            </Button>
          </div>

          <ul className="space-y-2">
            {pendingTasks.map(renderTaskItem)}
            {renderEditingView()}
          </ul>
        </div>

        <div className="bg-white rounded-lg p-3 shadow-sm flex-1 border border-[#E4E4E4]">
          <div className="flex mb-2">
            <div className="flex items-center gap-2 bg-[#F2F2F2] rounded-full px-2 py-1">
              <Circle className="h-3 w-3 text-gray-400 fill-current" />
              <span className="text-sm font-medium">Recruit Agent</span>
            </div>
          </div>

          <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-x-3">
            <Button 
              variant="outline" 
              className="justify-start gap-1 mb-2 bg-white border-[#E4E4E4] h-[40px]"
            >
              <Plus className="h-4 w-4" />
              New Agent
            </Button>
            {[1].map((index) => (
              <div key={index} className="invisible h-0" />
            ))}
          </div>

          <div className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-2">
            {[1, 2].map((index) => (
              <div key={index} className="rounded-lg p-3 border border-[#E4E4E4]">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Avatar className="h-8 w-8 bg-[#D9D9D9]">
                      <AvatarFallback>J</AvatarFallback>
                    </Avatar>
                    <div className="flex items-center gap-2">
                      <span className="font-medium">Associate_WebSearcher</span>
                      <Star className="h-4 w-4" />
                    </div>
                  </div>
                  <Button variant="ghost" size="icon" className="h-8 w-8">
                    <SquarePen className="h-4 w-4 text-[#979797]" />
                  </Button>
                </div>
                <p className="text-sm text-gray-600 mb-3">
                  Associate agent specialized in web searching tasks.
                </p>
                <div className="flex">
                  <div className="flex items-center gap-2 text-sm bg-[#F2F2F2] rounded-lg px-2 py-1">
                    <Search className="h-3 w-3" />
                    <span>Search & Visit Web</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
});
