import React, { useEffect, useState, useMemo } from 'react';
import { observer } from 'mobx-react-lite';
import { sessionStore } from '@/app/stores/sessionStore';
import LoadingSpinner from '@/components/layout/LoadingSpinner';
import { cn } from '@/lib/utils';

export const TimelineView = observer(() => {
  const [now, setNow] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  
  const viewModel = sessionStore.timelineViewModel;
  const viewError = sessionStore.viewErrors.get('timeline_view');

  const processedData = useMemo(() => {
    if (!viewModel || !viewModel.overallStartTime) {
      return null;
    }

    const { lanes, overallStartTime, overallEndTime, timeBreaks = [], isLive } = viewModel;
    const isConnected = sessionStore.ws?.readyState === WebSocket.OPEN;
    
    const overallStart = new Date(overallStartTime);
    // Key fix: only update in real-time if isLive and WebSocket is connected
    const overallEnd = isLive && isConnected ? now : new Date(overallEndTime || now);

    const timeBreaksWithDates = timeBreaks.map(br => ({
      start: new Date(br.breakStart),
      end: new Date(br.breakEnd),
      duration: br.duration,
    }));

    const totalBreakDuration = timeBreaks.reduce((sum, br) => sum + br.duration, 0);
    const actualDuration = (overallEnd.getTime() - overallStart.getTime()) / 1000 - totalBreakDuration;
    const totalVisualDuration = Math.max(30, actualDuration);

    const mapRealTimeToVisual = (realTimestamp: Date): number => {
      if (realTimestamp < overallStart) return 0;
      const effectiveTimestamp = realTimestamp > overallEnd ? overallEnd : realTimestamp;

      const rawElapsedSeconds = (effectiveTimestamp.getTime() - overallStart.getTime()) / 1000;
      
      let breaksBefore = 0;
      for (const br of timeBreaksWithDates) {
        if (effectiveTimestamp > br.end) {
          breaksBefore += br.duration;
        } else if (effectiveTimestamp > br.start) {
          // If the timestamp is inside a break, count the portion of the break that has passed
          breaksBefore += (effectiveTimestamp.getTime() - br.start.getTime()) / 1000;
        }
      }
      return Math.max(0, rawElapsedSeconds - breaksBefore);
    };

    return {
      totalVisualDuration,
      lanes,
      mapRealTimeToVisual,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewModel, now, sessionStore.ws?.readyState]);

  if (viewError) {
    return (
      <div className="w-full h-full bg-white rounded-lg border border-red-200 flex items-center justify-center p-4 text-center text-red-500">
        Error loading Timeline view: {viewError}
      </div>
    );
  }

  if (!processedData || !viewModel) {
    return (
      <div className="w-full h-full bg-white rounded-lg border border-[#E4E4E4] flex items-center justify-center p-4 text-center text-gray-500">
        <LoadingSpinner />
        <span className="ml-2">Waiting for timeline data...</span>
      </div>
    );
  }

  const { totalVisualDuration, lanes, mapRealTimeToVisual } = processedData;

  return (
    <div className="w-full h-full bg-white rounded-lg border border-[#E4E4E4] p-4 overflow-auto">
      <div className="relative space-y-4">
        {lanes
          .filter(lane => lane.agentId !== 'Partner' && lane.blocks.length > 0)
          .map(lane => (
            <div key={lane.agentId} className="flex items-center gap-4 h-8">
              <div className="w-40 text-sm font-medium truncate text-gray-700" title={lane.agentId}>
                {lane.agentId}
              </div>
              <div className="flex-1 h-full bg-gray-200/70 rounded-full relative overflow-hidden">
                {lane.blocks.map(block => {
                  const visualStart = mapRealTimeToVisual(new Date(block.startTime));
                  const isConnected = sessionStore.ws?.readyState === WebSocket.OPEN;
                  const liveEndPoint = viewModel.isLive && isConnected ? now : new Date(viewModel.overallEndTime || now);
                  const visualEnd = mapRealTimeToVisual(block.endTime ? new Date(block.endTime) : liveEndPoint);
                  
                  const startPercent = (visualStart / totalVisualDuration) * 100;
                  const widthPercent = ((visualEnd - visualStart) / totalVisualDuration) * 100;

                  const statusColor = 
                    block.status.includes('SUCCESS') ? 'bg-emerald-500' :
                    block.status.includes('ERROR') ? 'bg-red-500' :
                    block.status.includes('RUNNING') || block.status.includes('LAUNCHING') ? 'bg-blue-500' :
                    block.status.includes('CANCELLED') ? 'bg-slate-400' :
                    'bg-amber-500';
                  
                  // Infer blockType if not present, as backend might not send it yet.
                  const blockType = block.blockType || (() => {
                    const lowerModuleName = block.moduleName.toLowerCase();
                    if (lowerModuleName.startsWith('turn')) return 'turn';
                    if (lowerModuleName.startsWith('tool:') || lowerModuleName.startsWith('dispatch')) return 'tool';
                    return 'task';
                  })();

                  const positionClass = 
                    blockType === 'task' ? 'top-[25%]' :
                    blockType === 'turn' ? 'top-[50%]' :
                    'top-[75%]'; // tool

                  return (
                    <div
                      key={`${block.moduleId}-${block.startTime}-${blockType}`}
                      title={`${block.moduleName} (${block.status}) - ${blockType}`}
                      className={cn(
                        'absolute h-[6px] -translate-y-1/2 rounded-full opacity-80 hover:opacity-100 transition-all duration-200',
                        statusColor,
                        positionClass
                      )}
                      style={{ 
                        left: `${startPercent}%`, 
                        width: `${Math.max(0.2, widthPercent)}%`,
                        minWidth: '2px'
                      }}
                    >
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
      </div>
    </div>
  );
});

TimelineView.displayName = 'TimelineView';
