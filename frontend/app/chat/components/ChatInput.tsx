import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { observer } from 'mobx-react-lite';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { projectFilesStore } from '@/app/stores/projectFilesStore';
import { selectionStore } from '@/app/stores/selectionStore';
import {
  escapePath,
  extractFileTags,
  findActiveTriggerSegment,
  normalizeRelativePath,
  replaceSegment,
} from '@/app/utils/fileTagging';
import { ProjectFileMetadata } from '@/lib/api';
import { FileText, Folder, AlertCircle } from 'lucide-react';

interface ChatInputProps {
  currentInput: string;
  onInputChange: (value: string) => void;
  onKeyPress: (e: React.KeyboardEvent) => void;
  onSendMessage: () => void;
  isStreaming: boolean;
  isLoading: boolean;
  onStopExecution: () => void;
}

interface SuggestionItem {
  path: string;
  isDirectory: boolean;
}

interface ResolvedTag {
  rawPath: string;
  normalizedPath: string;
  metadata: ProjectFileMetadata | undefined;
}

function formatDisplayPath(metadata: ProjectFileMetadata | undefined, fallback: string): string {
  if (!metadata) {
    return fallback || '(unknown)';
  }
  return metadata.path;
}

export const ChatInput = observer(function ChatInput({
  currentInput,
  onInputChange,
  onKeyPress,
  onSendMessage,
  isStreaming,
  isLoading,
  onStopExecution,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const [cursorPosition, setCursorPosition] = useState(0);
  const [suggestions, setSuggestions] = useState<SuggestionItem[]>([]);
  const [activeSuggestionIndex, setActiveSuggestionIndex] = useState(0);
  const [activeTrigger, setActiveTrigger] = useState<ReturnType<typeof findActiveTriggerSegment>>(null);

  const selectedProjectId = selectionStore.selectedFile?.projectId
    ?? selectionStore.selectedProject?.projectId
    ?? null;

  useEffect(() => {
    if (selectedProjectId) {
      projectFilesStore.ensureLoaded(selectedProjectId).catch(() => undefined);
    }
  }, [selectedProjectId]);

  const projectFiles = selectedProjectId
    ? projectFilesStore.getFiles(selectedProjectId)
    : [];

  const resolvedTags: ResolvedTag[] = useMemo(() => {
    const parsed = extractFileTags(currentInput);
    const uniqueByPath = new Map<string, string>();
    parsed.forEach((tag) => {
      const normalized = normalizeRelativePath(tag.path);
      if (!uniqueByPath.has(normalized)) {
        uniqueByPath.set(normalized, tag.path);
      }
    });

    return Array.from(uniqueByPath.entries()).map(([normalizedPath, rawPath]) => {
      const metadata = projectFiles.find((file) => {
        const candidate = normalizeRelativePath(file.path);
        return candidate === normalizedPath;
      });
      return {
        rawPath,
        normalizedPath,
        metadata,
      };
    });
  }, [currentInput, projectFiles]);

  const unresolvedTags = resolvedTags.filter((tag) => !tag.metadata);
  const resolvedAttachments = resolvedTags.filter((tag) => tag.metadata);

  const updateSuggestions = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      setActiveTrigger(null);
      setSuggestions([]);
      return;
    }

    const trigger = findActiveTriggerSegment(currentInput, textarea.selectionStart ?? 0);
    setActiveTrigger(trigger);
    if (!trigger) {
      setSuggestions([]);
      return;
    }

    const query = normalizeRelativePath(trigger.query).toLowerCase();
    const filtered = projectFiles
      .filter((file) => {
        const candidate = normalizeRelativePath(file.path).toLowerCase();
        if (!query) {
          return true;
        }
        return candidate.includes(query);
      })
      .sort((a, b) => {
        if (a.is_directory === b.is_directory) {
          return a.path.localeCompare(b.path);
        }
        return a.is_directory ? -1 : 1;
      })
      .slice(0, 10)
      .map((file) => ({
        path: file.path,
        isDirectory: file.is_directory,
      }));

    setActiveSuggestionIndex(0);
    setSuggestions(filtered);
  }, [currentInput, projectFiles]);

  useEffect(() => {
    updateSuggestions();
  }, [cursorPosition, updateSuggestions]);

  const handleSelectSuggestion = useCallback((item: SuggestionItem) => {
    if (!activeTrigger) {
      return;
    }
    const textarea = textareaRef.current;
    const finalPath = item.isDirectory ? `${item.path}/` : item.path;
    const escaped = escapePath(finalPath);
    const nextValue = replaceSegment(currentInput, activeTrigger, escaped);
    onInputChange(nextValue);

    requestAnimationFrame(() => {
      if (textarea) {
        const nextCursor = activeTrigger.start + 1 + escaped.length;
        textarea.selectionStart = nextCursor;
        textarea.selectionEnd = nextCursor;
        setCursorPosition(nextCursor);
      }
    });

    setSuggestions([]);
    setActiveTrigger(null);
  }, [activeTrigger, currentInput, onInputChange]);

  const handleInputChange = useCallback((event: React.ChangeEvent<HTMLTextAreaElement>) => {
    onInputChange(event.target.value);
    setCursorPosition(event.target.selectionStart ?? event.target.value.length);
  }, [onInputChange]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (suggestions.length === 0) {
      return;
    }

    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setActiveSuggestionIndex((prev) => (prev + 1) % suggestions.length);
      return;
    }

    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActiveSuggestionIndex((prev) => (prev - 1 + suggestions.length) % suggestions.length);
      return;
    }

    if (event.key === 'Tab' || (event.key === 'Enter' && !event.shiftKey)) {
      event.preventDefault();
      const suggestion = suggestions[activeSuggestionIndex];
      if (suggestion) {
        handleSelectSuggestion(suggestion);
      }
      return;
    }

    if (event.key === 'Escape') {
      setSuggestions([]);
      setActiveTrigger(null);
    }
  }, [activeSuggestionIndex, handleSelectSuggestion, suggestions]);

  const handleSelectionChange = useCallback(() => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    setCursorPosition(textarea.selectionStart ?? 0);
  }, []);

  const handleSuggestionClick = useCallback((item: SuggestionItem) => {
    handleSelectSuggestion(item);
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.focus();
    }
  }, [handleSelectSuggestion]);

  return (
    <div className="p-3">
      <div className="bg-white rounded-lg border p-2 transition-colors focus-within:border-black">
        <div className="relative flex items-end gap-2">
          <Textarea
            ref={textareaRef}
            value={currentInput}
            onChange={handleInputChange}
            onKeyPress={onKeyPress}
            onKeyDown={handleKeyDown}
            onClick={handleSelectionChange}
            onKeyUp={handleSelectionChange}
            onSelect={handleSelectionChange}
            placeholder="Type a message. Use @ to attach project files."
            disabled={isStreaming || isLoading}
            className="flex-1 min-h-[96px] border-0 focus-visible:ring-0 focus-visible:ring-offset-0 shadow-none resize-none"
          />

          {isStreaming ? (
            <Button
              variant="ghost"
              size="icon"
              className="rounded-full bg-black hover:bg-black/90 !px-2 !py-1"
              onClick={onStopExecution}
            >
              <div className="w-3 h-3 bg-white" />
            </Button>
          ) : (
            <Button
              onClick={onSendMessage}
              disabled={!currentInput.trim() || isLoading}
            >
              Send
            </Button>
          )}

          {suggestions.length > 0 && (
            <div className="absolute left-0 right-24 top-full mt-2 z-10 rounded-md border bg-white shadow-lg overflow-hidden">
              {suggestions.map((item, index) => (
                <button
                  key={item.path}
                  type="button"
                  className={`flex w-full items-center gap-2 px-3 py-2 text-sm text-left hover:bg-gray-100 ${index === activeSuggestionIndex ? 'bg-gray-100' : ''}`}
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => handleSuggestionClick(item)}
                >
                  {item.isDirectory ? <Folder size={14} className="text-slate-500" /> : <FileText size={14} className="text-slate-500" />}
                  <span className="truncate">{item.path}{item.isDirectory ? '/' : ''}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        {resolvedAttachments.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-wide text-gray-400">Attachments</span>
            {resolvedAttachments.map((tag) => (
              <Badge key={tag.normalizedPath} variant="secondary" className="flex items-center gap-1">
                {tag.metadata?.is_directory ? <Folder size={12} /> : <FileText size={12} />}
                <span>{formatDisplayPath(tag.metadata, tag.rawPath)}</span>
              </Badge>
            ))}
          </div>
        )}

        {unresolvedTags.length > 0 && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-red-600">
            <AlertCircle size={14} />
            <span>Unresolved tags:</span>
            <TooltipProvider delayDuration={100}>
              {unresolvedTags.map((tag) => (
                <Tooltip key={tag.normalizedPath}>
                  <TooltipTrigger asChild>
                    <Badge variant="destructive" className="bg-red-100 text-red-700">
                      @{tag.rawPath || '(empty)'}
                    </Badge>
                  </TooltipTrigger>
                  <TooltipContent>
                    <span>Not found in project assets.</span>
                  </TooltipContent>
                </Tooltip>
              ))}
            </TooltipProvider>
          </div>
        )}
      </div>
    </div>
  );
});
