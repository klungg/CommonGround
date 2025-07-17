export interface Project {
  project_id: string
  name: string
  created_at: string
  updated_at: string
  deleted?: string
}

export interface Run {
  filename: string
  meta: {
    run_id: string
    description?: string
    [key: string]: unknown
  }
}

export interface ProjectWithRuns {
  project: Project
  runs: Run[]
}

export interface CreateProjectRequest {
  name: string
}

export interface UpdateProjectRequest {
  name?: string
  description?: string
  [key: string]: unknown
} 