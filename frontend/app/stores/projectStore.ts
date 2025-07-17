import { makeAutoObservable, runInAction, reaction } from 'mobx'
import { ProjectService } from '@/lib/api'
import { ProjectWithRuns, CreateProjectRequest, UpdateProjectRequest } from '@/lib/types'
import { selectionStore } from './selectionStore'
import { sessionStore } from './sessionStore'

class ProjectStore {
  projects: ProjectWithRuns[] = []
  loading: boolean = false
  error: string | null = null
  isInitialized: boolean = false

  constructor() {
    makeAutoObservable(this)
    this.setupReactions()
  }

  private setupReactions() {
    // Listen for changes to sessionStore.runCreatedCounter
    reaction(
      () => sessionStore.runCreatedCounter,
      (runCreatedCounter, prevRunCreatedCounter) => {
        if (runCreatedCounter > prevRunCreatedCounter) {
          console.log('Detected new run creation, silently refreshing projects...')
          this.loadProjects(true)
        }
      }
    )

    // Listen for changes to selectionStore.projectsRefreshCounter
    reaction(
      () => selectionStore.projectsRefreshCounter,
      (refreshCounter, prevRefreshCounter) => {
        if (refreshCounter > prevRefreshCounter) {
          this.loadProjects(true)
        }
      }
    )
  }

  async loadProjects(silentRefresh = false) {
    try {
      // 只有在没有初始化时或非静默刷新时才显示 loading
      if (!silentRefresh && !this.isInitialized) {
        runInAction(() => {
          this.loading = true
        })
      }
      
      runInAction(() => {
        this.error = null
      })
      
      const data = await ProjectService.getAllProjects()
      
      runInAction(() => {
        this.projects = data
        this.isInitialized = true
        
        // 同步项目数据到 selectionStore
        const projectsData = data.map(item => ({
          project_id: item.project.project_id,
          name: item.project.name,
          runs: item.runs,
        }))
        selectionStore.updateProjectsMap(projectsData)
      })
      
    } catch (err) {
      runInAction(() => {
        this.error = err instanceof Error ? err.message : 'Failed to load projects'
      })
    } finally {
      runInAction(() => {
        this.loading = false
      })
    }
  }

  async createProject(data: CreateProjectRequest) {
    const result = await ProjectService.createProject(data)
    // Removed: await this.loadProjects(true)
    return result
  }

  async updateProject(projectId: string, data: UpdateProjectRequest) {
    const result = await ProjectService.updateProject(projectId, data)
    // Removed: await this.loadProjects(true)
    return result
  }

  async deleteProject(projectId: string) {
    const result = await ProjectService.deleteProject(projectId)
    // Removed: await this.loadProjects(true)
    return result
  }

  async updateRun(runId: string, metadata: Record<string, unknown>) {
    const result = await ProjectService.updateRun(runId, metadata)
    // Removed: await this.loadProjects(true)
    return result
  }

  async renameRun(runId: string, newName: string) {
    const result = await ProjectService.renameRun(runId, newName)
    // Removed: await this.loadProjects(true)
    return result
  }

  async deleteRun(runId: string) {
    const result = await ProjectService.deleteRun(runId)
    // Removed: await this.loadProjects(true)
    return result
  }

  async moveRun(runId: string, fromProjectId: string, toProjectId: string) {
    const result = await ProjectService.moveRun(runId, fromProjectId, toProjectId)
    // Removed: await this.loadProjects(true)
    return result
  }

  // Initialization method, called only once when the application starts
  async initialize() {
    if (!this.isInitialized) {
      await this.loadProjects()
    }
  }
}

export const projectStore = new ProjectStore() 
