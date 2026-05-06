import { useMemo, useState } from 'react'
import type { GlobalSettingsData, ProviderDetail, StageName } from '../types'
import { Icon } from './Sidebar'

type SettingsTab = 'providers' | 'defaults' | 'templates'

type ProviderDraft = {
  label: string
  provider_type: string
  base_url: string
  api_key: string
  image_max_concurrency: string
}

type ProviderPreset = {
  title: string
  provider_type: string
  suggestedLabel: string
  suggestedBaseUrl: string
  description: string
}

const stageLabels: Record<StageName, string> = {
  brief_generation: '设计说明',
  image_prompt: '出图指令',
  image_generation: '候选图',
}

const settingsTabs: Array<{
  id: SettingsTab
  label: string
  caption: string
  icon: string
}> = [
  {
    id: 'providers',
    label: 'Provider',
    caption: '接入与实例',
    icon: 'api',
  },
  {
    id: 'defaults',
    label: '默认模型',
    caption: '全局继承',
    icon: 'model_training',
  },
  {
    id: 'templates',
    label: '模板',
    caption: 'Prompt 配置',
    icon: 'edit_note',
  },
]

const PROVIDER_TYPE_META: Record<
  string,
  {
    label: string
    hint: string
    badge: string
  }
> = {
  openai_compatible: {
    label: 'OpenAI 兼容',
    hint: '大多数第三方平台都走这个协议。',
    badge: '通用',
  },
  async_image: {
    label: '异步图片',
    hint: '适合需要提交任务并轮询结果的图片服务。',
    badge: '图片',
  },
  gemini_native: {
    label: 'Gemini 原生',
    hint: '适合 Gemini 官方原生接口。',
    badge: '官方',
  },
}

const providerPresets: ProviderPreset[] = [
  {
    title: '通用第三方 API',
    provider_type: 'openai_compatible',
    suggestedLabel: '新的 OpenAI 兼容 API',
    suggestedBaseUrl: 'https://your-provider.com/v1',
    description: 'OpenRouter、SiliconFlow、DeepInfra、火山方舟等大多都选这个。',
  },
  {
    title: '异步图片服务',
    provider_type: 'async_image',
    suggestedLabel: '新的异步图片 API',
    suggestedBaseUrl: 'https://your-async-image-provider.com/v1',
    description: '用于候选图阶段的排队式异步图片生成。',
  },
  {
    title: 'APIMart GPT-Image-2',
    provider_type: 'async_image',
    suggestedLabel: 'APIMart GPT-Image-2',
    suggestedBaseUrl: 'https://api.apimart.ai/v1',
    description: '使用通用异步图片协议，提交到 APIMart 后轮询任务结果。',
  },
  {
    title: 'Gemini 官方',
    provider_type: 'gemini_native',
    suggestedLabel: 'Gemini Official',
    suggestedBaseUrl: 'https://generativelanguage.googleapis.com',
    description: '官方 Gemini 原生接入。',
  },
]

const EMPTY_PROVIDER: ProviderDraft = {
  label: '',
  provider_type: 'openai_compatible',
  base_url: '',
  api_key: '',
  image_max_concurrency: '',
}

function templateDraftFromSettings(settings: GlobalSettingsData) {
  return {
    brief: settings.prompt_templates.brief_system_prompt || '',
    prompt: settings.prompt_templates.prompt_system_prompt || '',
  }
}

function defaultsDraftFromSettings(settings: GlobalSettingsData) {
  return {
    brief_provider: settings.defaults.brief_generation?.provider || '',
    brief_model: settings.defaults.brief_generation?.model || '',
    prompt_provider: settings.defaults.image_prompt?.provider || '',
    prompt_model: settings.defaults.image_prompt?.model || '',
    image_provider: settings.defaults.image_generation?.provider || '',
    image_model: settings.defaults.image_generation?.model || '',
  }
}

function providerMeta(providerType: string) {
  return PROVIDER_TYPE_META[providerType] ?? PROVIDER_TYPE_META.openai_compatible
}

function providerStages(provider: ProviderDetail): StageName[] {
  const allStages = provider.models.flatMap((model) => model.stages)
  const uniqueStages = Array.from(new Set(allStages)) as StageName[]
  if (uniqueStages.length > 0) return uniqueStages
  if (provider.provider_type === 'async_image') return ['image_generation']
  return ['brief_generation', 'image_prompt']
}

function maskDisplay(value: string) {
  return value || '未配置'
}

export default function GlobalSettings({
  open,
  settings,
  saving,
  onClose,
  onSaveTemplates,
  onSaveDefaults,
  onCreateProvider,
  onUpdateProvider,
  onDeleteProvider,
  onSyncProvider,
}: {
  open: boolean
  settings: GlobalSettingsData | null
  saving: boolean
  onClose: () => void
  onSaveTemplates: (payload: {
    brief_system_prompt?: string | null
    prompt_system_prompt?: string | null
  }) => Promise<void>
  onSaveDefaults: (payload: {
    brief_provider?: string | null
    brief_model?: string | null
    prompt_provider?: string | null
    prompt_model?: string | null
    image_provider?: string | null
    image_model?: string | null
  }) => Promise<void>
  onCreateProvider: (
    payload: Omit<ProviderDraft, 'image_max_concurrency'> & {
      image_max_concurrency?: number | null
    },
  ) => Promise<string>
  onUpdateProvider: (
    providerId: string,
    payload: Omit<ProviderDraft, 'api_key' | 'image_max_concurrency'> & {
      api_key?: string
      image_max_concurrency?: number | null
    },
  ) => Promise<string>
  onDeleteProvider: (providerId: string) => Promise<void>
  onSyncProvider: (providerId: string) => Promise<void>
}) {
  const [activeTab, setActiveTab] = useState<SettingsTab>('providers')
  const [templateDraft, setTemplateDraft] = useState<{
    brief: string
    prompt: string
  } | null>(null)
  const [defaultsDraft, setDefaultsDraft] = useState<{
    brief_provider: string
    brief_model: string
    prompt_provider: string
    prompt_model: string
    image_provider: string
    image_model: string
  } | null>(null)
  const [providerDraft, setProviderDraft] = useState<ProviderDraft>(EMPTY_PROVIDER)
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null)
  const [providerEditorOpen, setProviderEditorOpen] = useState(false)

  const providerOptions = useMemo(() => settings?.providers ?? [], [settings])

  const modelsForProvider = (providerId: string) =>
    providerOptions.find((provider) => provider.id === providerId)?.models ?? []

  const modelsForStage = (stage: StageName) =>
    providerOptions.flatMap((provider) =>
      provider.models
        .filter((model) => model.stages.includes(stage))
        .map((model) => ({
          provider: provider.id,
          providerLabel: provider.label,
          id: model.id,
          label: model.label,
        })),
    )

  if (!open || !settings) return null

  const templateValues = templateDraft ?? templateDraftFromSettings(settings)
  const defaults = defaultsDraft ?? defaultsDraftFromSettings(settings)
  const builtinProviders = settings.providers.filter((provider) => provider.builtin)
  const customProviders = settings.providers.filter((provider) => !provider.builtin)
  const currentProviderMeta = providerMeta(providerDraft.provider_type)
  const canSubmitProvider =
    !saving &&
    providerDraft.label.trim().length > 0 &&
    (editingProviderId !== null ||
      providerDraft.provider_type === 'gemini_native' ||
      providerDraft.base_url.trim().length > 0)

  function resetProviderDraft(next?: Partial<ProviderDraft>) {
    setProviderDraft({
      ...EMPTY_PROVIDER,
      ...next,
    })
  }

  function openCreateProvider(preset?: ProviderPreset) {
    setActiveTab('providers')
    setEditingProviderId(null)
    setProviderEditorOpen(true)
    resetProviderDraft(
      preset
        ? {
            label: preset.suggestedLabel,
            provider_type: preset.provider_type,
            base_url: preset.suggestedBaseUrl,
          }
        : EMPTY_PROVIDER,
    )
  }

  function openEditProvider(provider: ProviderDetail) {
    setActiveTab('providers')
    setEditingProviderId(provider.id)
    setProviderEditorOpen(true)
    setProviderDraft({
      label: provider.label,
      provider_type: provider.provider_type,
      base_url: provider.base_url,
      api_key: '',
      image_max_concurrency:
        provider.image_max_concurrency != null ? String(provider.image_max_concurrency) : '',
    })
  }

  function closeProviderEditor() {
    setProviderEditorOpen(false)
    setEditingProviderId(null)
    resetProviderDraft()
  }

  async function handleProviderSubmit(syncAfterSave = false) {
    const normalizedConcurrency = providerDraft.image_max_concurrency.trim()
      ? Math.max(1, Number.parseInt(providerDraft.image_max_concurrency, 10) || 1)
      : null
    let providerId: string
    if (editingProviderId) {
      providerId = await onUpdateProvider(editingProviderId, {
        ...providerDraft,
        api_key: providerDraft.api_key.trim() ? providerDraft.api_key : undefined,
        image_max_concurrency: normalizedConcurrency,
      })
    } else {
      providerId = await onCreateProvider({
        ...providerDraft,
        image_max_concurrency: normalizedConcurrency,
      })
    }
    if (syncAfterSave && providerId) {
      await onSyncProvider(providerId)
    }
    closeProviderEditor()
  }

  async function handleSaveDefaultsClick() {
    await onSaveDefaults({
      brief_provider: defaults.brief_provider,
      brief_model: defaults.brief_model,
      prompt_provider: defaults.prompt_provider,
      prompt_model: defaults.prompt_model,
      image_provider: defaults.image_provider,
      image_model: defaults.image_model,
    })
    setDefaultsDraft(null)
  }

  async function handleSaveTemplatesClick() {
    await onSaveTemplates({
      brief_system_prompt: templateValues.brief,
      prompt_system_prompt: templateValues.prompt,
    })
    setTemplateDraft(null)
  }

  function renderProviderEditorView() {
    return (
      <div className="space-y-5">
        <div className="flex items-center justify-between">
          <button
            onClick={closeProviderEditor}
            className="inline-flex items-center gap-2 rounded-lg border border-outline-variant/20 px-3 py-2 text-sm font-semibold text-on-surface transition-colors hover:bg-surface-container-high"
          >
            <Icon name="arrow_back" className="text-base" />
            返回 Provider 列表
          </button>
          <div className="rounded-full bg-primary/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-primary">
            {editingProviderId ? '编辑模式' : '新增模式'}
          </div>
        </div>

        <div className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.35fr)]">
          <section className="space-y-4">
            <div className="rounded-xl border border-primary/15 bg-primary/8 p-4">
              <div className="text-[11px] font-bold uppercase tracking-[0.22em] text-primary">
                {editingProviderId ? '编辑第三方 API' : '新增第三方 API'}
              </div>
              <h4 className="mt-2 text-2xl font-black tracking-tight text-on-surface">
                {editingProviderId ? providerDraft.label || '编辑 Provider' : '添加新的 Provider'}
              </h4>
              <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                这里是一个独立的二级视图。配置完成后保存，再回到 Provider 列表统一查看。
              </p>
            </div>

            <div className="rounded-xl border border-outline-variant/15 bg-surface-container p-4">
              <div className="text-sm font-bold text-on-surface">{currentProviderMeta.label}</div>
              <p className="mt-2 text-sm leading-6 text-on-surface-variant">
                {currentProviderMeta.hint}
              </p>
            </div>

            {!editingProviderId ? (
              <div className="rounded-xl border border-outline-variant/15 bg-surface-container p-4">
                <div className="text-sm font-bold text-on-surface">常见接入模板</div>
                <div className="mt-3 space-y-2">
                  {providerPresets.map((preset) => (
                    <button
                      key={preset.title}
                      onClick={() => openCreateProvider(preset)}
                      className="w-full rounded-xl border border-outline-variant/15 bg-surface-container-high/60 p-3 text-left transition-colors hover:border-primary/25 hover:bg-surface-container-high"
                    >
                      <div className="text-sm font-bold text-on-surface">{preset.title}</div>
                      <div className="mt-1 text-xs leading-5 text-on-surface-variant">
                        {preset.description}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </section>

          <section className="rounded-xl border border-outline-variant/15 bg-surface-container p-5">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="md:col-span-2">
                <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
                  显示名称
                </label>
                <input
                  value={providerDraft.label}
                  onChange={(event) =>
                    setProviderDraft((current) => ({
                      ...current,
                      label: event.target.value,
                    }))
                  }
                  className="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-3.5 py-3 text-sm text-on-surface outline-none transition-colors focus:border-primary/40"
                  placeholder="例如：OpenRouter 主账号"
                />
              </div>

              <div>
                <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
                  接入协议
                </label>
                <select
                  value={providerDraft.provider_type}
                  onChange={(event) =>
                    setProviderDraft((current) => ({
                      ...current,
                      provider_type: event.target.value,
                    }))
                  }
                  className="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-3.5 py-3 text-sm text-on-surface outline-none transition-colors focus:border-primary/40"
                >
                  <option value="openai_compatible">通用 OpenAI 兼容</option>
                  <option value="async_image">异步图片</option>
                  <option value="gemini_native">Gemini 原生</option>
                </select>
              </div>

              <div>
                <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
                  适用说明
                </label>
                <div className="rounded-xl border border-outline-variant/15 bg-surface-container-lowest/50 px-3.5 py-3 text-sm leading-6 text-on-surface-variant">
                  {providerDraft.provider_type === 'openai_compatible'
                    ? '如果是第三方聚合平台，通常就选这个。'
                    : providerDraft.provider_type === 'async_image'
                      ? '适合需要提交任务并轮询结果的图片服务，包括 APIMart GPT-Image-2。'
                      : '适合 Gemini 官方原生模型能力。'}
                </div>
              </div>

              <div className="md:col-span-2">
                <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
                  Base URL
                </label>
                <input
                  value={providerDraft.base_url}
                  onChange={(event) =>
                    setProviderDraft((current) => ({
                      ...current,
                      base_url: event.target.value,
                    }))
                  }
                  className="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-3.5 py-3 font-mono text-sm text-on-surface outline-none transition-colors focus:border-primary/40"
                  placeholder={
                    providerDraft.provider_type === 'openai_compatible'
                      ? 'https://your-provider.com/v1'
                      : providerDraft.provider_type === 'async_image'
                        ? 'https://your-async-image-provider.com/v1'
                        : 'https://generativelanguage.googleapis.com'
                  }
                />
              </div>

              <div className="md:col-span-2">
                <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
                  API Key
                </label>
                <input
                  value={providerDraft.api_key}
                  onChange={(event) =>
                    setProviderDraft((current) => ({
                      ...current,
                      api_key: event.target.value,
                    }))
                  }
                  className="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-3.5 py-3 font-mono text-sm text-on-surface outline-none transition-colors focus:border-primary/40"
                  placeholder={editingProviderId ? '留空则保留当前 API Key' : '粘贴新的 API Key'}
                />
              </div>

              <div className="md:col-span-2">
                <label className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
                  图片并发上限
                </label>
                <input
                  type="number"
                  min={1}
                  value={providerDraft.image_max_concurrency}
                  onChange={(event) =>
                    setProviderDraft((current) => ({
                      ...current,
                      image_max_concurrency: event.target.value,
                    }))
                  }
                  className="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-3.5 py-3 text-sm text-on-surface outline-none transition-colors focus:border-primary/40"
                  placeholder="留空则默认 1"
                />
                <div className="mt-2 text-xs leading-5 text-on-surface-variant">
                  控制同一个 Provider 在候选图阶段最多同时提交多少个任务。新接入的服务建议先从 1 开始。
                </div>
              </div>
            </div>

            <div className="mt-5 flex items-center justify-end gap-3">
              <button
                onClick={closeProviderEditor}
                className="rounded-xl border border-outline-variant/20 px-4 py-2.5 text-sm font-semibold text-on-surface transition-colors hover:bg-surface-container-high"
              >
                取消
              </button>
              <button
                disabled={!canSubmitProvider}
                onClick={() => void handleProviderSubmit(true)}
                className="rounded-xl border border-primary/20 bg-primary/10 px-5 py-2.5 text-sm font-bold text-primary transition-colors hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? '处理中…' : editingProviderId ? '保存并同步模型' : '新增并同步模型'}
              </button>
              <button
                disabled={!canSubmitProvider}
                onClick={() => void handleProviderSubmit()}
                className="rounded-xl bg-primary px-5 py-2.5 text-sm font-bold text-on-primary-fixed disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? '保存中…' : editingProviderId ? '保存修改' : '新增 Provider'}
              </button>
            </div>
          </section>
        </div>
      </div>
    )
  }

  function renderProviderOverview() {
    return (
      <div className="space-y-5">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-outline-variant/15 bg-surface-container px-4 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
              总 Provider
            </div>
            <div className="mt-1 text-2xl font-black text-on-surface">
              {builtinProviders.length + customProviders.length}
            </div>
          </div>
          <div className="rounded-xl border border-outline-variant/15 bg-surface-container px-4 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
              系统内置
            </div>
            <div className="mt-1 text-2xl font-black text-on-surface">
              {builtinProviders.length}
            </div>
          </div>
          <div className="rounded-xl border border-outline-variant/15 bg-surface-container px-4 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
              自定义实例
            </div>
            <div className="mt-1 text-2xl font-black text-primary">
              {customProviders.length}
            </div>
          </div>
        </div>

        <div className="rounded-xl border border-primary/15 bg-primary/8 px-4 py-3 text-sm leading-6 text-on-surface-variant">
          大多数第三方平台都可以按
          <span className="mx-1 font-bold text-primary">OpenAI 兼容协议</span>
          接进来。只有 OpenAI、Anthropic、Gemini 官方原生协议，以及特殊异步图片服务，才需要单独 provider 类型。
        </div>

        {renderProviderSection(
          '系统内置 Provider',
          builtinProviders,
          '默认提供的官方或开发用 provider。',
        )}
        {renderProviderSection(
          '自定义实例',
          customProviders,
          '你后面加的各种第三方 API 都会出现在这里。',
        )}
      </div>
    )
  }

  function renderProviderSection(title: string, providers: ProviderDetail[], emptyMessage: string) {
    return (
      <section>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h4 className="text-sm font-bold text-on-surface">{title}</h4>
            <p className="mt-1 text-xs text-on-surface-variant">{emptyMessage}</p>
          </div>
          {title === '自定义实例' ? (
            <button
              onClick={() => openCreateProvider()}
              className="rounded-lg bg-primary px-3 py-1.5 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim"
            >
              新增第三方 API
            </button>
          ) : null}
        </div>

        <div className="overflow-hidden rounded-xl border border-outline-variant/15 bg-surface-container">
          <div className="hidden grid-cols-[minmax(0,2fr)_1fr_1.6fr_72px_140px] gap-3 border-b border-outline-variant/10 bg-surface-container-high/60 px-4 py-2 text-[11px] font-bold uppercase tracking-[0.18em] text-outline lg:grid">
            <div>Provider</div>
            <div>协议</div>
            <div>Base URL</div>
            <div>模型</div>
            <div className="text-right">操作</div>
          </div>

          {providers.length === 0 ? (
            <div className="px-4 py-6 text-sm text-on-surface-variant">{title === '自定义实例' ? '还没有自定义 Provider。' : '暂无内容。'}</div>
          ) : (
            <div className="divide-y divide-outline-variant/10">
              {providers.map((provider) => {
                const meta = providerMeta(provider.provider_type)
                const stages = providerStages(provider)
                return (
                  <div key={provider.id} className="px-4 py-3">
                    <div className="grid gap-3 lg:grid-cols-[minmax(0,2fr)_1fr_1.6fr_72px_140px] lg:items-center">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="truncate text-sm font-bold text-on-surface">
                            {provider.label}
                          </span>
                          <span className="rounded-full border border-outline-variant/20 bg-surface-container-lowest/40 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-on-surface-variant">
                            {provider.builtin ? '内置' : '自定义'}
                          </span>
                          <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.14em] text-primary">
                            {meta.badge}
                          </span>
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1.5">
                          {stages.map((stage) => (
                            <span
                              key={stage}
                              className="rounded-full border border-outline-variant/15 px-2 py-0.5 text-[11px] text-on-surface-variant"
                            >
                              {stageLabels[stage]}
                            </span>
                          ))}
                        </div>
                      </div>

                      <div className="text-xs text-on-surface">
                        <div className="font-mono">{provider.provider_type}</div>
                        <div className="mt-1 text-[11px] text-on-surface-variant">{meta.hint}</div>
                      </div>

                      <div className="min-w-0 text-xs">
                        <div className="truncate font-mono text-on-surface">
                          {provider.base_url || '本地'}
                        </div>
                        <div className="mt-1 truncate font-mono text-[11px] text-on-surface-variant">
                          {maskDisplay(provider.api_key_masked)}
                        </div>
                        <div className="mt-1 text-[11px] text-on-surface-variant">
                          图片并发上限：{provider.image_max_concurrency ?? 1}
                        </div>
                      </div>

                      <div className="text-sm font-bold text-on-surface">{provider.models.length}</div>

                      <div className="flex items-center justify-start gap-2 lg:justify-end">
                        <button
                          onClick={() => void onSyncProvider(provider.id)}
                          className="rounded-lg border border-outline-variant/20 px-2.5 py-1.5 text-[11px] font-bold text-on-surface transition-colors hover:bg-surface-container-high"
                        >
                          同步
                        </button>
                        <button
                          onClick={() => openEditProvider(provider)}
                          className="rounded-lg border border-outline-variant/20 p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface"
                        >
                          <Icon name="edit" className="text-sm" />
                        </button>
                        {!provider.builtin ? (
                          <button
                            onClick={() => void onDeleteProvider(provider.id)}
                            className="rounded-lg border border-error/20 p-1.5 text-error transition-colors hover:bg-error/10"
                          >
                            <Icon name="delete" className="text-sm" />
                          </button>
                        ) : null}
                      </div>
                    </div>

                    {provider.last_error ? (
                      <div className="mt-3 rounded-lg border border-error/20 bg-error/10 px-3 py-2 text-[11px] text-error">
                        最近同步错误：{provider.last_error}
                      </div>
                    ) : null}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </section>
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-3 backdrop-blur-sm md:p-4">
      <div className="flex h-[90vh] w-full max-w-[1480px] overflow-hidden rounded-2xl border border-outline-variant/15 bg-surface-container-low shadow-2xl shadow-black/40">
        <aside className="hidden w-56 shrink-0 border-r border-outline-variant/10 bg-surface-container px-4 py-5 lg:flex lg:flex-col">
          <div className="mb-6">
            <div className="text-[11px] font-bold uppercase tracking-[0.24em] text-primary">
              Settings
            </div>
            <h2 className="mt-2 text-xl font-black tracking-tight text-on-surface">全局设置</h2>
            <p className="mt-2 text-xs leading-5 text-on-surface-variant">
              设置会继续扩展，所以先按页签结构组织。
            </p>
          </div>

          <nav className="space-y-1.5">
            {settingsTabs.map((tab) => {
              const active = tab.id === activeTab
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left transition-colors ${
                    active
                      ? 'bg-primary/12 text-on-surface'
                      : 'text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface'
                  }`}
                >
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-container-highest">
                    <Icon name={tab.icon} className="text-lg" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-bold">{tab.label}</span>
                    <span className="block text-[11px] text-on-surface-variant">{tab.caption}</span>
                  </span>
                </button>
              )
            })}
          </nav>

          <button
            onClick={onClose}
            className="mt-auto rounded-xl border border-outline-variant/20 px-3 py-2 text-sm font-semibold text-on-surface transition-colors hover:bg-surface-container-high"
          >
            关闭
          </button>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-start justify-between border-b border-outline-variant/10 px-5 py-4 md:px-6">
            <div>
              <div className="mb-1 flex items-center gap-2 lg:hidden">
                {settingsTabs.map((tab) => {
                  const active = tab.id === activeTab
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] ${
                        active
                          ? 'bg-primary/12 text-primary'
                          : 'bg-surface-container text-on-surface-variant'
                      }`}
                    >
                      {tab.label}
                    </button>
                  )
                })}
              </div>
              <h3 className="text-lg font-black tracking-tight text-on-surface md:text-xl">
                {activeTab === 'providers'
                  ? providerEditorOpen
                    ? editingProviderId
                      ? '编辑 Provider'
                      : '新增第三方 API'
                    : 'Provider 与接入实例'
                  : activeTab === 'defaults'
                    ? '默认模型继承'
                    : 'Prompt 模板'}
              </h3>
              <p className="mt-1 text-xs leading-5 text-on-surface-variant md:text-sm">
                {activeTab === 'providers'
                  ? providerEditorOpen
                    ? '你现在处于 Provider 的二级编辑视图，保存后会返回列表。'
                    : 'Provider 放在最上层，新增第三方 API 作为二级操作进入。'
                  : activeTab === 'defaults'
                    ? '按阶段配置默认 provider 和模型。'
                    : '管理设计说明与出图指令的底层模板。'}
              </p>
            </div>
            <button
              onClick={onClose}
              className="rounded-xl border border-outline-variant/20 px-3 py-2 text-sm font-semibold text-on-surface transition-colors hover:bg-surface-container-high lg:hidden"
            >
              关闭
            </button>
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5 md:px-6">
            {activeTab === 'providers' ? (
              providerEditorOpen ? renderProviderEditorView() : renderProviderOverview()
            ) : null}

            {activeTab === 'defaults' ? (
              <div className="space-y-5">
                <div className="rounded-xl border border-outline-variant/15 bg-surface-container px-4 py-3 text-sm leading-6 text-on-surface-variant">
                  这里是全局默认模型。条目没有单独覆盖时，会从这里继承。
                </div>

                <div className="grid gap-4 xl:grid-cols-3">
                  {(
                    [
                      ['brief_generation', defaults.brief_provider, defaults.brief_model],
                      ['image_prompt', defaults.prompt_provider, defaults.prompt_model],
                      ['image_generation', defaults.image_provider, defaults.image_model],
                    ] as const
                  ).map(([stage, providerValue, modelValue]) => (
                    <div key={stage} className="rounded-xl border border-outline-variant/15 bg-surface-container p-4">
                      <div className="mb-3 text-sm font-bold text-on-surface">{stageLabels[stage]}</div>
                      <div className="space-y-3">
                        <select
                          value={providerValue}
                          onChange={(event) =>
                            setDefaultsDraft((current) => ({
                              ...(current ?? defaults),
                              [`${stage === 'brief_generation' ? 'brief' : stage === 'image_prompt' ? 'prompt' : 'image'}_provider`]:
                                event.target.value,
                              [`${stage === 'brief_generation' ? 'brief' : stage === 'image_prompt' ? 'prompt' : 'image'}_model`]:
                                '',
                            }))
                          }
                          className="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-3.5 py-2.5 text-sm text-on-surface outline-none transition-colors focus:border-primary/40"
                        >
                          <option value="">请选择 provider</option>
                          {providerOptions.map((provider) => (
                            <option key={provider.id} value={provider.id}>
                              {provider.label}
                            </option>
                          ))}
                        </select>

                        <select
                          value={modelValue}
                          onChange={(event) =>
                            setDefaultsDraft((current) => ({
                              ...(current ?? defaults),
                              [`${stage === 'brief_generation' ? 'brief' : stage === 'image_prompt' ? 'prompt' : 'image'}_model`]:
                                event.target.value,
                            }))
                          }
                          className="w-full rounded-xl border border-outline-variant/20 bg-surface-container-lowest px-3.5 py-2.5 text-sm text-on-surface outline-none transition-colors focus:border-primary/40"
                        >
                          <option value="">请选择模型</option>
                          {modelsForProvider(providerValue)
                            .filter((model) => model.stages.includes(stage))
                            .map((model) => (
                              <option key={model.id} value={model.id}>
                                {model.label}
                              </option>
                            ))}
                        </select>

                        <div className="rounded-lg border border-outline-variant/15 bg-surface-container-lowest/50 px-3 py-2">
                          <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
                            可选模型
                          </div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {modelsForStage(stage).slice(0, 8).map((model) => (
                              <span
                                key={`${model.provider}:${model.id}`}
                                className="rounded-full border border-outline/20 px-2 py-0.5 text-[11px] text-on-surface-variant"
                              >
                                {model.providerLabel} · {model.label}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex justify-end">
                  <button
                    disabled={saving}
                    onClick={() => void handleSaveDefaultsClick()}
                    className="rounded-xl bg-primary px-4 py-2.5 text-sm font-bold text-on-primary-fixed disabled:opacity-50"
                  >
                    {saving ? '保存中…' : '保存默认模型'}
                  </button>
                </div>
              </div>
            ) : null}

            {activeTab === 'templates' ? (
              <div className="space-y-5">
                <div className="rounded-xl border border-outline-variant/15 bg-surface-container px-4 py-3 text-sm leading-6 text-on-surface-variant">
                  这里管理系统提示词，不和 Provider 或默认模型混在一起。
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                  <div className="flex h-[360px] flex-col rounded-xl border border-outline-variant/15 bg-surface-container">
                    <div className="border-b border-outline-variant/10 px-4 py-3">
                      <div className="text-sm font-bold text-on-surface">设计说明模板</div>
                      <div className="mt-1 font-mono text-[11px] text-on-surface-variant">
                        brief_system_prompt
                      </div>
                    </div>
                    <textarea
                      value={templateValues.brief}
                      onChange={(event) =>
                        setTemplateDraft((current) => ({
                          ...(current ?? templateValues),
                          brief: event.target.value,
                        }))
                      }
                      className="flex-1 resize-none bg-surface-container-lowest/60 p-4 font-mono text-[12px] leading-6 text-on-surface-variant outline-none"
                    />
                  </div>

                  <div className="flex h-[360px] flex-col rounded-xl border border-outline-variant/15 bg-surface-container">
                    <div className="border-b border-outline-variant/10 px-4 py-3">
                      <div className="text-sm font-bold text-on-surface">出图指令模板</div>
                      <div className="mt-1 font-mono text-[11px] text-on-surface-variant">
                        prompt_system_prompt
                      </div>
                    </div>
                    <textarea
                      value={templateValues.prompt}
                      onChange={(event) =>
                        setTemplateDraft((current) => ({
                          ...(current ?? templateValues),
                          prompt: event.target.value,
                        }))
                      }
                      className="flex-1 resize-none bg-surface-container-lowest/60 p-4 font-mono text-[12px] leading-6 text-on-surface-variant outline-none"
                    />
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    disabled={saving}
                    onClick={() => void handleSaveTemplatesClick()}
                    className="rounded-xl bg-primary px-4 py-2.5 text-sm font-bold text-on-primary-fixed disabled:opacity-50"
                  >
                    {saving ? '保存中…' : '保存模板'}
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
