import type {
  ItemSummary,
  ProviderSummary,
  TaskSummary,
  WorkspacePayload,
} from '../types'

const API_BASE = '/api'

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function fetchTasks(): Promise<TaskSummary[]> {
  const payload = await request<{ tasks: TaskSummary[] }>('/tasks')
  return payload.tasks
}

export async function fetchTask(taskId: string): Promise<TaskSummary> {
  return request<TaskSummary>(`/tasks/${taskId}`)
}

export async function fetchTaskItems(taskId: string): Promise<ItemSummary[]> {
  const payload = await request<{ task_id: string; items: ItemSummary[] }>(
    `/tasks/${taskId}/items`,
  )
  return payload.items
}

export async function fetchTaskItem(
  taskId: string,
  itemId: string,
): Promise<ItemSummary> {
  return request<ItemSummary>(`/tasks/${taskId}/items/${itemId}`)
}

export async function fetchProviders(): Promise<ProviderSummary[]> {
  const payload = await request<{ providers: ProviderSummary[] }>('/providers')
  return payload.providers
}

export async function fetchTaskItemWorkspace(
  taskId: string,
  itemId: string,
): Promise<WorkspacePayload> {
  return request<WorkspacePayload>(`/tasks/${taskId}/items/${itemId}/workspace`)
}
