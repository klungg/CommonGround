import { makeAutoObservable, runInAction, reaction } from 'mobx'
import { ProjectService, ProjectFileMetadata } from '@/lib/api'
import { selectionStore } from './selectionStore'

interface ProjectFilesState {
  files: ProjectFileMetadata[]
}

class ProjectFilesStore {
  private filesByProject = new Map<string, ProjectFilesState>()
  private loadingProjects = new Set<string>()
  private uploadingProjects = new Set<string>()
  private errorsByProject = new Map<string, string | null>()
  private debounceTimers = new Map<string, ReturnType<typeof setTimeout>>()

  constructor() {
    makeAutoObservable(this)
    reaction(
      () => selectionStore.selectedProject?.projectId,
      (projectId) => {
        if (projectId) {
          this.ensureLoaded(projectId)
        }
      }
    )
  }

  getFiles(projectId: string): ProjectFileMetadata[] {
    return this.filesByProject.get(projectId)?.files ?? []
  }

  isLoading(projectId: string): boolean {
    return this.loadingProjects.has(projectId)
  }

  isUploading(projectId: string): boolean {
    return this.uploadingProjects.has(projectId)
  }

  getError(projectId: string): string | null {
    return this.errorsByProject.get(projectId) ?? null
  }

  async ensureLoaded(projectId: string, force = false) {
    const hasData = this.filesByProject.has(projectId)
    if (!force && hasData && !this.loadingProjects.has(projectId)) {
      return
    }
    await this.load(projectId)
  }

  async load(projectId: string) {
    this.loadingProjects.add(projectId)
    this.errorsByProject.delete(projectId)
    try {
      const response = await ProjectService.listProjectFiles(projectId)
      runInAction(() => {
        this.filesByProject.set(projectId, { files: response.files })
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load files'
      runInAction(() => {
        this.errorsByProject.set(projectId, message)
      })
    } finally {
      runInAction(() => {
        this.loadingProjects.delete(projectId)
      })
    }
  }

  async upload(projectId: string, files: File[]): Promise<ProjectFileMetadata[]> {
    if (!files.length) {
      return []
    }
    this.uploadingProjects.add(projectId)
    try {
      const response = await ProjectService.uploadProjectFiles(projectId, files)
      runInAction(() => {
        this.mergeFiles(projectId, response.uploaded)
      })
      this.queueReload(projectId, 0)
      return response.uploaded
    } finally {
      runInAction(() => {
        this.uploadingProjects.delete(projectId)
      })
    }
  }

  async deleteFile(projectId: string, path: string) {
    await ProjectService.deleteProjectFile(projectId, path)
    runInAction(() => {
      const current = this.getFiles(projectId)
      this.filesByProject.set(projectId, {
        files: current.filter((file) => file.path !== path)
      })
    })
    this.queueReload(projectId)
  }

  async renameFile(projectId: string, oldPath: string, newPath: string) {
    const response = await ProjectService.renameProjectFile(projectId, oldPath, newPath)
    runInAction(() => {
      const updatedFiles = this.getFiles(projectId)
        .filter((file) => file.path !== response.old_path)
      updatedFiles.push(response.file)
      this.filesByProject.set(projectId, {
        files: this.sortFiles(updatedFiles)
      })
    })
    this.queueReload(projectId)
    return response
  }

  handleWebsocketUpdate(payload: {
    project_id: string
    change_type: string
    details: Record<string, unknown>
  }) {
    const { project_id: projectId, change_type: changeType, details } = payload
    if (!projectId) return

    switch (changeType) {
      case 'created': {
        const files = (details.files as ProjectFileMetadata[]) ?? []
        if (files.length) {
          runInAction(() => {
            this.mergeFiles(projectId, files)
          })
        }
        break
      }
      case 'deleted': {
        const path = String(details.path ?? '')
        if (path) {
          runInAction(() => {
            const current = this.getFiles(projectId)
            this.filesByProject.set(projectId, {
              files: current.filter((file) => file.path !== path)
            })
          })
        }
        break
      }
      case 'renamed': {
        const file = details.file as ProjectFileMetadata | undefined
        const oldPath = String(details.old_path ?? '')
        if (file && oldPath) {
          runInAction(() => {
            const current = this.getFiles(projectId).filter((entry) => entry.path !== oldPath)
            current.push(file)
            this.filesByProject.set(projectId, { files: this.sortFiles(current) })
          })
        }
        break
      }
      case 'synced': {
        // Debounce reloads to avoid hammering the API when the monitor sends bursts
        this.queueReload(projectId)
        break
      }
      default:
        break
    }
  }

  private mergeFiles(projectId: string, files: ProjectFileMetadata[]) {
    const current = this.getFiles(projectId)
    const currentByPath = new Map(current.map((file) => [file.path, file]))
    files.forEach((file) => {
      currentByPath.set(file.path, file)
    })
    const merged = Array.from(currentByPath.values())
    this.filesByProject.set(projectId, { files: this.sortFiles(merged) })
  }

  private sortFiles(files: ProjectFileMetadata[]) {
    return files.slice().sort((a, b) => {
      if (a.is_directory === b.is_directory) {
        return a.path.localeCompare(b.path)
      }
      return a.is_directory ? -1 : 1
    })
  }

  private queueReload(projectId: string, delayMs = 500) {
    if (this.debounceTimers.has(projectId)) {
      clearTimeout(this.debounceTimers.get(projectId)!)
    }
    const timer = setTimeout(() => {
      this.ensureLoaded(projectId, true)
      this.debounceTimers.delete(projectId)
    }, delayMs)
    this.debounceTimers.set(projectId, timer)
  }
}

export const projectFilesStore = new ProjectFilesStore()
