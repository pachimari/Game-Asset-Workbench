export type StageName =
  | 'brief_generation'
  | 'image_prompt'
  | 'image_generation'

export type StageStatus =
  | 'draft'
  | 'brief_generated'
  | 'brief_approved'
  | 'prompt_generated'
  | 'prompt_approved'
  | 'image_generating'
  | 'image_generated'
  | 'completed'
  | 'failed'
  | 'archived'

export type ModelOverride = {
  provider: string | null
  model: string | null
}

export type TaskSummary = {
  task_id: string
  task_name: string
  project_background: string
  style_requirements: string
  asset_domain: string
  created_at: string
  updated_at: string
  status: string
  item_count: number
  style_spec_ref: string
  runtime_config_ref: string
  items_summary?: Record<string, number>
  model_overrides: Record<StageName, ModelOverride>
}

export type ItemSummary = {
  item_id: string
  asset_type: string
  title: string
  description: string
  category: string
  extra_context: string
  status: StageStatus
  created_at: string
  updated_at: string
  current_versions: Record<StageName, string | null>
  model_overrides: Record<StageName, ModelOverride>
  runtime_overrides: {
    image_aspect_ratio: string | null
    image_resolution: string | null
  }
  preview_image_url?: string | null
}

export type ProviderSummary = {
  id: string
  label: string
  provider_type: string
  base_url: string
  model_count: number
  builtin: boolean
  last_synced_at: string | null
  last_error: string | null
}

export type CandidateImage = {
  candidate_id: string
  image_path: string | null
  image_url: string | null
  source_url?: string | null
}

export type CandidateVersion = {
  version: string
  provider: string | null
  model: string | null
  created_at: string | null
  is_current: boolean
  async_job: {
    status?: string
    progress?: number
    task_id?: string
    error?: string
  } | null
  candidates: CandidateImage[]
}

export type ArtifactSnapshot = {
  version: string
  provider: string | null
  model: string | null
  created_at: string | null
  input: Record<string, unknown> | null
  output: Record<string, unknown> | null
}

export type WorkspacePayload = {
  task_id: string
  item_id: string
  status: StageStatus
  current_versions: Record<StageName, string | null>
  brief: ArtifactSnapshot | null
  prompt: ArtifactSnapshot | null
  current_image_version: string | null
  candidate_pool: {
    approved_image_url: string | null
    versions: CandidateVersion[]
  }
  events: Array<Record<string, unknown>>
  chat: Array<Record<string, unknown>>
}

export type ModelEntry = {
  id: string
  label: string
  stages: string[]
  compatibility: string
}

export type ProviderDetail = {
  id: string
  label: string
  provider_type: string
  base_url: string
  builtin: boolean
  api_key_masked: string
  models: ModelEntry[]
  last_synced_at: string | null
  last_error: string | null
}

export type GlobalSettingsData = {
  defaults: Record<StageName, { provider: string; model: string }>
  prompt_templates: {
    brief_system_prompt: string
    prompt_system_prompt: string
  }
  providers: ProviderDetail[]
}
