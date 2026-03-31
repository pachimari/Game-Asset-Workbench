import type {
  GlobalSettingsData,
  ItemSummary,
  ProviderSummary,
  TaskSummary,
  WorkspacePayload,
} from '../types'

const API_BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `API request failed: ${response.status}`)
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

export async function fetchSettings(): Promise<GlobalSettingsData> {
  return request<GlobalSettingsData>('/settings')
}

export async function createTask(payload: {
  task_name: string
  project_background: string
  style_requirements: string
  asset_domain: string
}): Promise<TaskSummary> {
  return request<TaskSummary>('/tasks', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function deleteTask(taskId: string): Promise<{ ok: boolean; task_id: string }> {
  return request(`/tasks/${taskId}`, {
    method: 'DELETE',
  })
}

export async function updateTask(
  taskId: string,
  payload: {
    task_name?: string | null
    project_background?: string | null
    style_requirements?: string | null
    asset_domain?: string | null
    image_aspect_ratio?: string | null
    image_resolution?: string | null
  },
): Promise<TaskSummary> {
  return request<TaskSummary>(`/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function createTaskItem(
  taskId: string,
  payload: {
    asset_type: string
    title: string
    description: string
    category: string
    extra_context: string
    image_aspect_ratio?: string | null
    image_resolution?: string | null
  },
): Promise<ItemSummary> {
  return request<ItemSummary>(`/tasks/${taskId}/items`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateTaskItem(
  taskId: string,
  itemId: string,
  payload: Record<string, unknown>,
): Promise<ItemSummary> {
  return request<ItemSummary>(`/tasks/${taskId}/items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function runItemStep(
  taskId: string,
  itemId: string,
  step: string,
): Promise<{ result: Record<string, unknown>; workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/steps/${step}/run`, {
    method: 'POST',
    body: JSON.stringify({ source: 'web' }),
  })
}

export async function approveItemStep(
  taskId: string,
  itemId: string,
  step: string,
): Promise<{ result: Record<string, unknown>; workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/steps/${step}/approve`, {
    method: 'POST',
    body: JSON.stringify({ source: 'web' }),
  })
}

export async function rollbackItemStep(
  taskId: string,
  itemId: string,
  step: string,
): Promise<{ result: Record<string, unknown>; workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/steps/${step}/rollback`, {
    method: 'POST',
    body: JSON.stringify({ source: 'web' }),
  })
}

export async function pollItemImage(
  taskId: string,
  itemId: string,
  version?: string,
): Promise<{ result: Record<string, unknown>; workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/image/poll`, {
    method: 'POST',
    body: JSON.stringify({ source: 'web', version }),
  })
}

export async function cancelItemImage(
  taskId: string,
  itemId: string,
): Promise<{ result: Record<string, unknown>; workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/image/cancel`, {
    method: 'POST',
    body: JSON.stringify({ source: 'web' }),
  })
}

export async function savePromptTemplates(payload: {
  brief_system_prompt?: string | null
  prompt_system_prompt?: string | null
}): Promise<GlobalSettingsData> {
  return request<GlobalSettingsData>('/settings/templates', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function saveGlobalDefaults(payload: {
  brief_provider?: string | null
  brief_model?: string | null
  prompt_provider?: string | null
  prompt_model?: string | null
  image_provider?: string | null
  image_model?: string | null
}): Promise<GlobalSettingsData> {
  return request<GlobalSettingsData>('/settings/defaults', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function createProvider(payload: {
  label: string
  provider_type: string
  base_url: string
  api_key: string
}): Promise<GlobalSettingsData> {
  return request<GlobalSettingsData>('/providers', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateProvider(
  providerId: string,
  payload: {
    label?: string
    provider_type?: string
    base_url?: string
    api_key?: string
  },
): Promise<GlobalSettingsData> {
  return request<GlobalSettingsData>(`/providers/${providerId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export async function deleteProvider(providerId: string): Promise<GlobalSettingsData> {
  return request<GlobalSettingsData>(`/providers/${providerId}`, {
    method: 'DELETE',
  })
}

export async function syncProviderModels(providerId: string): Promise<GlobalSettingsData> {
  return request<GlobalSettingsData>(`/providers/${providerId}/sync-models`, {
    method: 'POST',
  })
}
