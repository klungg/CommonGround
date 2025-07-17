import { makeAutoObservable } from 'mobx';
import { removeIicExtension } from '@/lib/utils';

export interface SelectedFile {
  runId: string;
  filename: string;
  projectId: string;
  projectName: string;
}

// 1. 新增 SelectedProject 接口
export interface SelectedProject {
  projectId: string;
  projectName: string;
}

class SelectionStore {
  selectedFile: SelectedFile | null = null;
  selectedProject: SelectedProject | null = null; // 2. 新增 selectedProject 状态
  // Counter to trigger a global refresh of the project list
  projectsRefreshCounter: number = 0;
  
  // Added: Manage project expansion state
  openProjects: Record<string, boolean> = {};
  
  // Added: Map for project data to get the latest project name
  private projectsMap: Map<string, string> = new Map(); // projectId -> projectName
  // Added: Map for file data to get the latest file name
  private runsMap: Map<string, string> = new Map(); // runId -> filename
  // Added: Map for display names to get the latest display name
  private runsDisplayNameMap: Map<string, string> = new Map(); // runId -> display_name

  constructor() {
    makeAutoObservable(this);
  }

  // Added: Update the project data maps
  updateProjectsMap(projects: { project_id: string; name: string; runs?: { filename: string; meta: { run_id: string, display_name?: string } }[] }[]) {
    this.projectsMap.clear();
    this.runsMap.clear();
    this.runsDisplayNameMap.clear(); // <-- Clear
    
    projects.forEach(project => {
      this.projectsMap.set(project.project_id, project.name);
      
      // Also update the runs data maps
      if (project.runs) {
        project.runs.forEach(run => {
          this.runsMap.set(run.meta.run_id, run.filename);
          if (run.meta.display_name) {
            this.runsDisplayNameMap.set(run.meta.run_id, run.meta.display_name); // <-- Populate
          }
        });
      }
    });
    
    // Update the project and file names for the currently selected item
    this.syncProjectNames();
  }

  // Added: Sync project and file names
  private syncProjectNames() {
    if (this.selectedProject) {
      const latestProjectName = this.projectsMap.get(this.selectedProject.projectId);
      if (latestProjectName && latestProjectName !== this.selectedProject.projectName) {
        this.selectedProject = {
          ...this.selectedProject,
          projectName: latestProjectName,
        };
      }
    }

    if (this.selectedFile) {
      const latestProjectName = this.projectsMap.get(this.selectedFile.projectId);
      const latestFileName = this.runsMap.get(this.selectedFile.runId);
      
      let needsUpdate = false;
      const updatedFile = { ...this.selectedFile };
      
      if (latestProjectName && latestProjectName !== this.selectedFile.projectName) {
        updatedFile.projectName = latestProjectName;
        needsUpdate = true;
      }
      
      if (latestFileName && latestFileName !== this.selectedFile.filename) {
        updatedFile.filename = latestFileName;
        needsUpdate = true;
      }
      
      if (needsUpdate) {
        this.selectedFile = updatedFile;
      }
    }
  }

  // 3. Implement the missing setSelectedProject method
  setSelectedProject(project: SelectedProject | null) {
    this.selectedProject = project;
    // When only a project is selected, clear the selected file to avoid UI state confusion.
    if (project) {
        this.selectedFile = null;
    }
  }

  setSelectedFile(file: SelectedFile | null) {
    this.selectedFile = file;
    // 4. When a file is selected, also update the selected project.
    if (file) {
      this.selectedProject = {
        projectId: file.projectId,
        projectName: file.projectName,
      };
    }
  }

  clearSelection() {
    // 5. Clear both file and project selections simultaneously.
    this.selectedFile = null;
    this.selectedProject = null;
  }

  // 触发全局项目列表刷新
  triggerProjectsRefresh() {
    this.projectsRefreshCounter += 1;
  }

  get hasSelection(): boolean {
    // A selection is defined as either a file or a project being selected.
    return this.selectedFile !== null || this.selectedProject !== null;
  }

  get displayProjectName(): string {
    // Prioritize getting the project name from the latest project data.
    const selectedProjectId = this.selectedFile?.projectId || this.selectedProject?.projectId;
    if (selectedProjectId) {
      const latestProjectName = this.projectsMap.get(selectedProjectId);
      if (latestProjectName) {
        return latestProjectName;
      }
    }
    
    // Fall back to the cached project name.
    return this.selectedFile?.projectName || this.selectedProject?.projectName || 'Default Project';
  }

  get displayFileName(): string {
    // Prioritize getting the file name from the latest file data.
    if (this.selectedFile) {
      // 1. Prioritize getting from the display name map.
      const displayName = this.runsDisplayNameMap.get(this.selectedFile.runId);
      if (displayName) {
        return displayName; // display_name does not need the extension removed.
      }
      
      // 2. Second, get from the run filename map.
      const latestFileName = this.runsMap.get(this.selectedFile.runId);
      if (latestFileName) {
        return removeIicExtension(latestFileName);
      }
      // 3. Finally, fall back to the cached file name.
      return removeIicExtension(this.selectedFile.filename);
    }
    
    // Default file name.
    return removeIicExtension('new file');
  }

  // Added: Toggle project expansion state.
  toggleProject(projectId: string) {
    this.openProjects = {
      ...this.openProjects,
      [projectId]: !this.openProjects[projectId]
    };
  }

  // Added: Set project expansion state.
  setProjectOpen(projectId: string, isOpen: boolean) {
    this.openProjects = {
      ...this.openProjects,
      [projectId]: isOpen
    };
  }

  // Added: Get project expansion state.
  isProjectOpen(projectId: string): boolean {
    return !!this.openProjects[projectId];
  }
}

export const selectionStore = new SelectionStore();
