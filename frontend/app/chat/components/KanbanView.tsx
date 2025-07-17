import React from 'react';
import { sessionStore, EnrichedWorkModule } from '@/app/stores/sessionStore';
import { observer } from 'mobx-react-lite';
import LoadingSpinner from '@/components/layout/LoadingSpinner';

interface KanbanViewProps {
  runId: string;
  groupMode: 'task' | 'agent';
}

interface ColumnColor {
  bg: string;
  border: string;
  text: string;
  dot: string;
}

const KanbanColumn = ({ title, tasks, color }: { title: string, tasks: EnrichedWorkModule[], color: ColumnColor }) => (
  <div className="flex-1 min-w-[180px] max-w-[320px] px-4 first:pl-0 last:pr-0">
    <div className={`${color.bg} ${color.border} ${color.text} rounded-lg px-3 py-2 mb-3 border`}>
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${color.dot}`}></div>
        <span className="font-medium">{title}</span>
      </div>
    </div>
    <div className="space-y-3">
      {tasks.map(task => (
        <div key={task.module_id} className="border border-gray-200 rounded-lg p-3 bg-gray-50">
          <div className="text-sm font-medium mb-1">{task.name}</div>
          <p className="text-xs text-gray-600 mb-2">{task.description}</p>
          {task.live_status_summary && <p className="text-xs text-blue-600">Status: {task.live_status_summary}</p>}
        </div>
      ))}
    </div>
  </div>
);

export const KanbanView = observer(({ groupMode }: KanbanViewProps) => {
  const kanbanViewModel = sessionStore.kanbanViewModel;
  const viewError = sessionStore.viewErrors.get('kanban_view');

  if (viewError) {
    return (
      <div className="w-full h-full bg-white rounded-lg border border-red-200 flex items-center justify-center p-4 text-center text-red-500">
        Error loading Kanban board: {viewError}
      </div>
    );
  }

  if (!kanbanViewModel) {
    return (
      <div className="w-full h-full bg-white rounded-lg border border-[#E4E4E4] flex items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  const renderByStatus = () => {
    const { pending, ongoing, pending_review, completed } = kanbanViewModel.view_by_status;
    const statusColumns = [
      { title: 'Pending', tasks: pending, color: { bg: 'bg-slate-100', border: 'border-slate-200', text: 'text-slate-800', dot: 'bg-slate-400' } },
      { title: 'Ongoing', tasks: ongoing, color: { bg: 'bg-blue-100', border: 'border-blue-200', text: 'text-blue-800', dot: 'bg-blue-500' } },
      { title: 'In Review', tasks: pending_review, color: { bg: 'bg-amber-100', border: 'border-amber-200', text: 'text-amber-800', dot: 'bg-amber-500' } },
      { title: 'Completed', tasks: completed, color: { bg: 'bg-emerald-100', border: 'border-emerald-200', text: 'text-emerald-800', dot: 'bg-emerald-500' } },
    ];
    return statusColumns.map(col => <KanbanColumn key={col.title} {...col} />);
  };

  const renderByAgent = () => {
    const agentEntries = Object.entries(kanbanViewModel.view_by_agent);
    const colors = [
      { bg: 'bg-violet-100', border: 'border-violet-200', text: 'text-violet-800', dot: 'bg-violet-500' },
      { bg: 'bg-sky-100', border: 'border-sky-200', text: 'text-sky-800', dot: 'bg-sky-500' },
      { bg: 'bg-teal-100', border: 'border-teal-200', text: 'text-teal-800', dot: 'bg-teal-500' },
      { bg: 'bg-rose-100', border: 'border-rose-200', text: 'text-rose-800', dot: 'bg-rose-500' },
    ];
    return agentEntries.map(([agentId, tasks], index) => (
      <KanbanColumn key={agentId} title={agentId} tasks={tasks} color={colors[index % colors.length]} />
    ));
  };

  return (
    <div className="w-full overflow-x-auto">
      <div className="flex min-h-[400px]">
        {groupMode === 'task' ? renderByStatus() : renderByAgent()}
      </div>
    </div>
  );
});
