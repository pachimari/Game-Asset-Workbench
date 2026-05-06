import type {
  GlobalSettingsData,
  ItemSummary,
  ProviderSummary,
  TaskSummary,
  WorkspacePayload,
} from '../types'

const API_BASE = '/api'

function authHeaders(): HeadersInit {
  if (typeof window === 'undefined') {
    return {}
  }
  const token = window.localStorage.getItem('ai-icon-pipeline-api-token')?.trim()
  if (!token) {
    return {}
  }
  return {
    Authorization: `Bearer ${token}`,
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
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

function parseDownloadFilename(disposition: string | null, fallback: string) {
  if (!disposition) return fallback
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1])
  }
  const plainMatch = disposition.match(/filename="?([^"]+)"?/i)
  if (plainMatch?.[1]) {
    return plainMatch[1]
  }
  return fallback
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

export async function downloadTaskStarredImages(taskId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/tasks/${taskId}/exports/starred-images.zip`, {
    headers: {
      ...authHeaders(),
    },
  })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `API request failed: ${response.status}`)
  }
  const blob = await response.blob()
  const filename = parseDownloadFilename(
    response.headers.get('content-disposition'),
    `${taskId}-starred-images.zip`,
  )
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
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
    image_generation_mode?: 'single' | 'grid_sheet' | null
    grid_rows?: number | null
    grid_cols?: number | null
    grid_padding?: number | null
    grid_gap?: number | null
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

export async function editTaskItemBrief(
  taskId: string,
  itemId: string,
  payload: {
    title?: string | null
    description?: string | null
    visual_focus?: string | null
    keywords?: string[] | null
    note?: string | null
  },
): Promise<{ result: Record<string, unknown>; workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/brief/edit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function editTaskItemPrompt(
  taskId: string,
  itemId: string,
  payload: {
    prompt?: string | null
    negative_prompt?: string | null
    note?: string | null
  },
): Promise<{ result: Record<string, unknown>; workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/prompt/edit`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function selectTaskItemVersion(
  taskId: string,
  itemId: string,
  step: string,
  version: string,
): Promise<{ result: Record<string, unknown>; workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/steps/${step}/select-version`, {
    method: 'POST',
    body: JSON.stringify({ version, source: 'web' }),
  })
}

export async function toggleTaskItemCandidateStar(
  taskId: string,
  itemId: string,
  version: string,
  starred: boolean,
): Promise<{ workspace: WorkspacePayload }> {
  return request(`/tasks/${taskId}/items/${itemId}/image/star`, {
    method: 'POST',
    body: JSON.stringify({ version, starred, source: 'web' }),
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

export async function runTaskPipeline(
  taskId: string,
  payload: {
    auto_approve?: boolean
    image_concurrency?: number | null
  } = {},
): Promise<{ result: Record<string, unknown>; task: TaskSummary; items: ItemSummary[] }> {
  return request(`/tasks/${taskId}/pipeline/run`, {
    method: 'POST',
    body: JSON.stringify({
      source: 'web',
      auto_approve: payload.auto_approve ?? true,
      image_concurrency: payload.image_concurrency ?? undefined,
    }),
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
  image_max_concurrency?: number | null
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
    image_max_concurrency?: number | null
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
