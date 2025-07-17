import React, { useState, useMemo, useEffect, useRef } from 'react';
import { observer } from 'mobx-react-lite';
import { sessionStore } from '@/app/stores/sessionStore';
import { TurnBubble } from './TurnBubble';
// import { Input } from '@/components/ui/input';
import { FilterCombobox } from './FilterCombobox';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';
import { Node } from 'reactflow';
import { Turn } from '@/app/stores/sessionStore';

interface ConversationDetailViewProps {
  turns: Turn[];

  highlightedNodeId: string | null;
  onClose: () => void;
  onNodeIdClick: (event: React.MouseEvent, node: Node) => void;
}

export const ConversationDetailView = observer(({ turns, highlightedNodeId, onClose, onNodeIdClick }: ConversationDetailViewProps) => {
  const [agentFilter, setAgentFilter] = useState('');
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const agentOptions = useMemo(() => {
    const agentIds = new Set(turns.map(turn => turn.agent_info.agent_id));
    const options = Array.from(agentIds).map(id => ({ value: id, label: id }));
    options.unshift({ value: 'all', label: 'All Agents' });
    return options;
  }, [turns]);

  const filteredTurns = useMemo(() => {
    if (!agentFilter || agentFilter === 'all') {
      return turns;
    }
    return turns.filter(turn => turn.agent_info.agent_id === agentFilter);
  }, [turns, agentFilter]);

  useEffect(() => {
    if (highlightedNodeId && scrollContainerRef.current) {
      const elementToScrollTo = document.getElementById(highlightedNodeId);
      if (elementToScrollTo) {
        elementToScrollTo.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } else {
        // If the element is not found, it might be filtered out or the ID doesn't match.
        console.warn(`[ConversationDetailView] Element with ID "${highlightedNodeId}" not found for scrolling. It might be filtered out.`);
      }
    }
  }, [highlightedNodeId, agentFilter]);

  const comboboxStyle = useMemo(() => {
    const placeholderText = "Filter by agent...";
    
    const longestText = agentOptions.reduce((longest, option) => {
      return option.label.length > longest.length ? option.label : longest;
    }, placeholderText);

    if (typeof document === 'undefined') {
      return { width: '200px' }; // Default for SSR
    }

    const span = document.createElement('span');
    span.style.fontSize = '0.875rem';
    span.style.fontFamily = 'inherit';
    span.style.fontWeight = '500';
    span.style.visibility = 'hidden';
    span.style.position = 'absolute';
    span.style.whiteSpace = 'nowrap';
    span.innerText = longestText;
    
    document.body.appendChild(span);
    const textWidth = span.getBoundingClientRect().width;
    document.body.removeChild(span);

    // Button: px-3 (12px * 2), icon: w-4 (16px) + ml-4 (16px)
    const totalWidth = textWidth + 24 + 16 + 16;
    
    return { width: `${totalWidth}px` };
  }, [agentOptions]);

  const handleBubbleNodeClick = (nodeId: string) => {
    const node = sessionStore.findNodeInFlow(nodeId);
    if (node) {
      onNodeIdClick({} as React.MouseEvent, { ...node, position: { x: 0, y: 0 } });
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="flex p-2 border-y bg-white items-center gap-2">
        <p className="text-sm font-medium">Filter by agent:</p>
        <FilterCombobox
          options={agentOptions}
          value={agentFilter}
          onChange={setAgentFilter}
          placeholder="All Agents"
          searchPlaceholder="Search agents..."
          noResultsMessage="No agents found."
          style={comboboxStyle}
        />
        <Button variant="ghost" size="icon" onClick={onClose} className="h-8 w-8 ml-auto">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {filteredTurns.map(turn => (
          <TurnBubble
            key={turn.turn_id} // Use turn_id as key
            turn={turn}
            isHighlighted={turn.turn_id === highlightedNodeId} // Highlighting logic should also be based on turn_id
            onNodeIdClick={handleBubbleNodeClick}
          />
        ))}
      </div>
    </div>
  );
});
