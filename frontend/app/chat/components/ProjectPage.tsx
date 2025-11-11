import React, { useState, useEffect, useRef } from 'react';
import { observer } from 'mobx-react-lite';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { SidebarTrigger } from '@/components/ui/sidebar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { MoreHorizontal, Trash2, SquarePen, X, Check } from 'lucide-react';
import { projectStore } from '@/app/stores/projectStore';
import { selectionStore } from '@/app/stores/selectionStore';
import LoadingSpinner from '@/components/layout/LoadingSpinner';
import { ProjectWithRuns } from '@/lib/types';
import { projectFilesStore } from '@/app/stores/projectFilesStore';
import { ProjectService, ProjectFileMetadata } from '@/lib/api';
import { ChatInput } from './ChatInput';

interface ProjectPageProps {
  currentInput: string;
  onInputChange: (value: string) => void;
  onSendMessage: () => void;
  onKeyPress: (e: React.KeyboardEvent) => void;
  isLoading: boolean;
}

export const ProjectPage = observer(function ProjectPage({
  currentInput,
  onInputChange,
  onSendMessage,
  onKeyPress,
  isLoading,
}: ProjectPageProps) {
  // Get data directly from the store, call methods via projectStore.methodName()
  const { projects, loading } = projectStore;
  
  // Get current project info from the selected project
  const currentProject = projects.find((p: ProjectWithRuns) => 
    p.project.project_id === selectionStore.selectedProject?.projectId
  );
  const projectId = selectionStore.selectedProject?.projectId;
  
  const [isEditingName, setIsEditingName] = useState(false);
  const [editingProjectName, setEditingProjectName] = useState('');
  // const [instructions, setInstructions] = useState('');
  // const [isEditingInstructions, setIsEditingInstructions] = useState(false);
  // const [editingInstructions, setEditingInstructions] = useState('');
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  // Check if it's the default project
  const isDefaultProject = currentProject?.project.project_id === 'default';
  
  // Current project name - fully based on selectionStore to ensure real-time sync
  const projectName = selectionStore.selectedProject?.projectName || 'Unknown Project';

  // When the project changes, update local state
  useEffect(() => {
    if (currentProject && selectionStore.selectedProject) {
      // Ensure selectionStore has the latest project information
      if (selectionStore.selectedProject.projectId === currentProject.project.project_id) {
        // If the project name in selectionStore differs from the database, prefer the name from selectionStore (the latest value during an update)
        const nameToUse = selectionStore.selectedProject.projectName;
        setEditingProjectName(nameToUse);
        
        // Debug info
        console.log('ProjectPage sync:', {
          storeProjectName: selectionStore.selectedProject.projectName,
          dbProjectName: currentProject.project.name,
          usingName: nameToUse
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject, selectionStore.selectedProject]);

  // Handle project name update
  const handleUpdateProjectName = async () => {
    if (!currentProject || !editingProjectName.trim() || isDefaultProject) return;
    
    try {
      setIsUpdating(true);
      
      console.log('ProjectPage updating:', editingProjectName.trim());
      
              // Only call the API; subsequent sync relies entirely on projectStore.updateProject() → loadProjects() → updateProjectsMap()
              await projectStore.updateProject(currentProject.project.project_id, { 
          name: editingProjectName.trim() 
        });
      
      setIsEditingName(false);
    } catch (error) {
      console.error('Failed to update project name:', error);
      // A toast notification for the error can be added here
    } finally {
      setIsUpdating(false);
    }
  };

  // Handle project deletion
  const handleDeleteProject = async () => {
    if (!currentProject || isDefaultProject) return;
    
    try {
      setIsUpdating(true);
      await projectStore.deleteProject(currentProject.project.project_id);
      
      // Clear selection state after successful deletion
      selectionStore.clearSelection();
      
      // Trigger a global project list refresh to ensure AppSidebar updates immediately
      selectionStore.triggerProjectsRefresh();
      
      // Close the delete confirmation dialog
      setIsDeleteDialogOpen(false);
      
      // Optional: navigate back to home page or other pages
      // router.push('/');
    } catch (error) {
      console.error('Failed to delete project:', error);
      // A toast notification for the error can be added here
    } finally {
      setIsUpdating(false);
    }
  };

  // Cancel editing project name - use the currently displayed name, not the old one from the database
  const handleCancelEditName = () => {
    setEditingProjectName(projectName);
    setIsEditingName(false);
  };

  // Start editing project name
  const handleStartEditName = () => {
    if (isDefaultProject) return;
    setEditingProjectName(projectName);
    setIsEditingName(true);
  };

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (projectId) {
      projectFilesStore.ensureLoaded(projectId);
    }
  }, [projectId]);

  const handleUploadButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    if (!projectId) return;
    const files = Array.from(event.target.files ?? []);
    if (!files.length) return;

    try {
      await projectFilesStore.upload(projectId, files);
    } catch (error) {
      console.error('Failed to upload files:', error);
    } finally {
      event.target.value = '';
    }
  };

  const handleDownload = async (file: ProjectFileMetadata) => {
    if (!projectId || file.is_directory) return;
    try {
      const blob = await ProjectService.downloadProjectFile(projectId, file.path);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = file.name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Failed to download file:', error);
    }
  };

  const handleDelete = async (file: ProjectFileMetadata) => {
    if (!projectId || file.is_directory) return;
    const confirmed = window.confirm(`Delete ${file.name}?`);
    if (!confirmed) return;
    try {
      await projectFilesStore.deleteFile(projectId, file.path);
    } catch (error) {
      console.error('Failed to delete file:', error);
    }
  };

  const handleRename = async (file: ProjectFileMetadata) => {
    if (!projectId || file.is_directory) return;
    const newName = window.prompt('Enter new file name', file.name);
    if (!newName || newName === file.name) return;

    const directory = file.path.includes('/') ? file.path.slice(0, file.path.lastIndexOf('/')) : '';
    const newPath = directory ? `${directory}/${newName}` : newName;

    try {
      await projectFilesStore.renameFile(projectId, file.path, newPath);
    } catch (error) {
      console.error('Failed to rename file:', error);
    }
  };

  const formatSize = (size: number | null) => {
    if (size === null || size === undefined) return '-';
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatTimestamp = (iso: string) => {
    try {
      const date = new Date(iso);
      return date.toLocaleString();
    } catch {
      return iso;
    }
  };

  const projectFiles = projectId ? projectFilesStore.getFiles(projectId) : [];
  const filesLoading = projectId ? projectFilesStore.isLoading(projectId) : false;
  const filesUploading = projectId ? projectFilesStore.isUploading(projectId) : false;
  const filesError = projectId ? projectFilesStore.getError(projectId) : null;

  // If project data is loading, show loading state.
  // But if there is already project data, it means an update is in progress, so don't show full-screen loading.
  if (loading && projects.length === 0) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-shrink-0 h-12 bg-white flex items-center justify-between px-3">
          <div className="flex items-center gap-2">
            <SidebarTrigger />
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  // If data loading is complete but the project is not found, show an error state
  if (!currentProject) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-shrink-0 h-12 bg-white flex items-center justify-between px-3">
          <div className="flex items-center gap-2">
            <SidebarTrigger />
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-gray-500">
            <p>Project not found</p>
            <Button 
              variant="outline" 
              onClick={() => selectionStore.clearSelection()}
              className="mt-4"
            >
              Back to Home
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-shrink-0 h-12 bg-white flex items-center justify-between px-3">
        <div className="flex items-center gap-2">
          <SidebarTrigger />
        </div>
      </div>
      <div className="flex-3  flex flex-col items-center justify-center">
        <div className="flex flex-col h-full p-6 md:p-8 lg:p-12 bg-white text-black">
          {/* Header */}
          <header className="flex justify-between items-start mb-6">
            <div className="flex items-center gap-2">
              {isEditingName ? (
                <>
                  <Input
                    value={editingProjectName}
                    onChange={(e) => setEditingProjectName(e.target.value)}
                    className="text-3xl font-bold h-auto"
                    autoFocus
                    disabled={isUpdating}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        handleUpdateProjectName();
                      } else if (e.key === 'Escape') {
                        handleCancelEditName();
                      }
                    }}
                  />
                  <Button 
                    variant="outline" 
                    className="h-8 w-10" 
                    size="icon" 
                    onClick={handleCancelEditName}
                    disabled={isUpdating}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  <Button 
                    className="h-8 w-10 bg-black hover:bg-black/80" 
                    size="icon" 
                    onClick={handleUpdateProjectName}
                    disabled={isUpdating || !editingProjectName.trim()}
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                </>
              ) : (
                <div className="group relative flex items-center gap-3">
                  <h1
                    className={`text-3xl font-bold ${
                      isDefaultProject ? 'cursor-default' : 'cursor-pointer'
                    }`}
                    onClick={handleStartEditName}
                  >
                    {projectName}
                  </h1>
                  {!isDefaultProject && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={handleStartEditName}
                    >
                      <SquarePen className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              )}
            </div>
            
            {/* Only show the actions menu for non-default projects */}
            {!isDefaultProject && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" size="icon" disabled={isUpdating}>
                    <MoreHorizontal className="h-5 w-5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem 
                    className="text-red-600 focus:text-red-600 focus:bg-red-50"
                    onClick={() => {
                      // Use setTimeout to ensure DropdownMenu is fully closed before opening the Dialog
                      setTimeout(() => {
                        setIsDeleteDialogOpen(true);
                      }, 0);
                    }}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    <span>Delete Project</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </header>

          <main className="w-[600px] flex-1 space-y-8">
            {/* Chat Input Section */}
            <div>
              <h2 className="text-lg font-semibold mb-3">What can I help you?</h2>
              <ChatInput
                currentInput={currentInput}
                onInputChange={onInputChange}
                onKeyPress={onKeyPress}
                onSendMessage={onSendMessage}
                isStreaming={false}
                isLoading={isLoading}
                onStopExecution={() => {}}
              />
            </div>

            {/* Project Instructions Section */}
            {/* <div>
              <div className="group relative flex items-center gap-3 mb-3">
                <h2 className="text-lg font-semibold">Project Instructions</h2>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => {
                    setEditingInstructions(instructions);
                    setIsEditingInstructions(true);
                  }}
                >
                  <SquarePen className="h-4 w-4" />
                </Button>
              </div>
              {isEditingInstructions ? (
                <div className="space-y-3">
                  <Textarea
                    value={editingInstructions}
                    onChange={(e) => setEditingInstructions(e.target.value)}
                    placeholder="Provide instructions for the agent. Be clear and concise."
                    className="min-h-[120px] w-full rounded-lg border p-4"
                    autoFocus
                  />
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={() => setIsEditingInstructions(false)}>Cancel</Button>
                    <Button onClick={() => {
                      setInstructions(editingInstructions);
                      setIsEditingInstructions(false);
                    }}>Save</Button>
                  </div>
                </div>
              ) : (
                <div
                  className="text-gray-500 min-h-[40px] cursor-text"
                  onClick={() => {
                    setEditingInstructions(instructions);
                    setIsEditingInstructions(true);
                  }}
                >
                  {instructions || 'Click to add project instructions.'}
                </div>
              )}
            </div> */}

            {projectId && (
              <div>
                <div className="flex justify-between items-center mb-3">
                  <h2 className="text-lg font-semibold">Project Files</h2>
                  <div className="flex items-center gap-3">
                    {filesUploading && <span className="text-sm text-gray-500">Uploading...</span>}
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={handleFileUpload}
                    />
                    <Button variant="outline" onClick={handleUploadButtonClick} disabled={filesUploading}>
                      + Upload Files
                    </Button>
                  </div>
                </div>

                {filesError && (
                  <div className="mb-3 text-sm text-destructive">{filesError}</div>
                )}

                {filesLoading ? (
                  <div className="border rounded-lg p-6 text-center text-gray-500">
                    Loading project files...
                  </div>
                ) : projectFiles.length === 0 ? (
                  <div className="border rounded-lg p-6 text-center text-gray-400">
                    <p>No files have been added yet.</p>
                  </div>
                ) : (
                  <div className="border rounded-lg overflow-hidden">
                    <table className="min-w-full divide-y divide-gray-200 text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left font-semibold text-gray-600">Name</th>
                          <th className="px-4 py-2 text-left font-semibold text-gray-600">Size</th>
                          <th className="px-4 py-2 text-left font-semibold text-gray-600">Modified</th>
                          <th className="px-4 py-2 text-right font-semibold text-gray-600">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {projectFiles.map((file) => (
                          <tr key={file.path}>
                            <td className="px-4 py-2 text-gray-900">
                              {file.is_directory ? `📁 ${file.name}` : file.name}
                            </td>
                            <td className="px-4 py-2 text-gray-500">{file.is_directory ? '-' : formatSize(file.size)}</td>
                            <td className="px-4 py-2 text-gray-500">{formatTimestamp(file.modified_at)}</td>
                            <td className="px-4 py-2 text-right">
                              <div className="flex justify-end gap-2">
                                {!file.is_directory && (
                                  <Button size="sm" variant="ghost" onClick={() => handleDownload(file)}>
                                    Download
                                  </Button>
                                )}
                                {!file.is_directory && (
                                  <Button size="sm" variant="ghost" onClick={() => handleRename(file)}>
                                    Rename
                                  </Button>
                                )}
                                {!file.is_directory && (
                                  <Button size="sm" variant="ghost" onClick={() => handleDelete(file)}>
                                    Delete
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Delete Project Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Project</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>
              Are you sure you want to delete the project &quot;{projectName}&quot;? 
              This will delete all associated files and cannot be undone.
            </p>
          </div>
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setIsDeleteDialogOpen(false)}
              disabled={isUpdating}
            >
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleDeleteProject}
              disabled={isUpdating}
            >
              {isUpdating ? 'Deleting...' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
});
