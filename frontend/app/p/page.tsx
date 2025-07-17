'use client';

import { useSearchParams, useRouter } from 'next/navigation';
import { useEffect, useState, useCallback } from 'react';
import { observer } from 'mobx-react-lite';

import { selectionStore } from '@/app/stores/selectionStore';
import { sessionStore } from '@/app/stores/sessionStore';
import { ProjectPage } from '@/app/chat/components/ProjectPage';
import { projectStore } from '@/app/stores/projectStore';
import LoadingSpinner from '@/components/layout/LoadingSpinner';
import { useLocalObservable } from 'mobx-react-lite';

// ====================================================================
// 1. Create Loader component
// ====================================================================
const ProjectPageLoader = observer(() => {
  const searchParams = useSearchParams();
  const router = useRouter();
  const projectId = searchParams.get('id');

  useEffect(() => {
    if (!projectId) {
      window.location.href = '/';
    }
  }, [projectId]);

  const { projects, loading } = projectStore;

  const store = useLocalObservable(() => ({
    currentInput: '',
    isLoading: false,
    isCreatingRun: false,
    setCurrentInput(text: string) { this.currentInput = text; },
    setIsLoading(loading: boolean) { this.isLoading = loading; },
    setIsCreatingRun(creating: boolean) { this.isCreatingRun = creating; }
  }));

  // Initialize project selection state
  useEffect(() => {
    if (!loading && projectId && projects.length > 0) {
      const project = projects.find(p => p.project.project_id === projectId);
      if (project) {
        selectionStore.setSelectedProject({
          projectId: project.project.project_id,
          projectName: project.project.name
        });
      }
    }
  }, [projectId, projects, loading]);

  const sendMessage = useCallback(async () => {
    if (!store.currentInput.trim() || store.isLoading || store.isCreatingRun || !projectId) return;
    const messageToSend = store.currentInput;
    store.setCurrentInput('');
    try {
        store.setIsCreatingRun(true);
        console.log(`Creating new run in project: ${projectId}`);
        const newRunId = await sessionStore.createRun('partner_interaction', projectId);
        store.setIsLoading(true);
        await sessionStore.sendMessage(messageToSend, newRunId);
        router.push(`/r?id=${newRunId}`);
    } catch (error) {
        console.error('Failed to create run or send message:', error);
        if (error instanceof Error) {
          sessionStore.error = error.message;
        } else {
          sessionStore.error = 'An unknown error occurred.';
        }
    } finally {
        store.setIsLoading(false);
        store.setIsCreatingRun(false);
    }
  }, [store, projectId, router]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }, [sendMessage]);

  // Rendering logic
  if (!projectId) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <LoadingSpinner />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <LoadingSpinner />
      </div>
    );
  }

  const project = projects.find(p => p.project.project_id === projectId);
  if (!project) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <div className="text-center text-gray-500">
          <h2 className="text-xl font-semibold mb-2">Project not found</h2>
          <p>The project you&apos;re looking for doesn&apos;t exist or has been deleted.</p>
        </div>
      </div>
    );
  }

  return (
    <ProjectPage
      currentInput={store.currentInput}
      onInputChange={(val) => store.setCurrentInput(val)}
      onSendMessage={sendMessage}
      onKeyPress={handleKeyPress}
      isLoading={store.isLoading || store.isCreatingRun}
    />
  );
});

// ====================================================================
// 2. Original Page component
// ====================================================================
export default function ProjectPageRoute() {
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
  }, []);

  if (!isClient) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <LoadingSpinner />
      </div>
    );
  }

  return <ProjectPageLoader />;
} 