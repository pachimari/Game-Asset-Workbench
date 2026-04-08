import { useState } from 'react'
import clsx from 'clsx'
import type { CandidateVersion, GlobalSettingsData, ItemSummary, TaskSummary, WorkspacePayload } from '../types'
import { formatRelativeDate, statusLabel } from '../lib/display'
import { Icon } from './Sidebar'

type OutputTab = 'overview' | 'brief' | 'prompt' | 'candidate'
type StageKey = 'brief_generation' | 'image_prompt' | 'image_generation'
const IMAGE_ASPECT_RATIO_OPTIONS = ['1:1', '3:4', '4:3', '2:3', '3:2', '9:16', '16:9', '21:9']
const IMAGE_RESOLUTION_OPTIONS = ['auto', '512', '1K', '2K', '4K']

function modelLabel(value: string | null | undefined) {
  if (!value) return '未配置'
  return value.replace(/^models\//, '')
}

function outputRecord(snapshot: WorkspacePayload['brief' | 'prompt']) {
  return (snapshot?.output ?? {}) as Record<string, unknown>
}

function inputRecord(snapshot: WorkspacePayload['brief' | 'prompt']) {
  return (snapshot?.input ?? {}) as Record<string, unknown>
}

function stringList(value: unknown) {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string')
}

function splitTags(value: string | null | undefined) {
  if (!value) return []
  return value
    .split(/[，,、|/]/)
    .map((part) => part.trim())
    .filter(Boolean)
}

function stageLabel(stage: StageKey) {
  return (
    {
      brief_generation: '设计说明',
      image_prompt: '出图指令',
      image_generation: '候选图',
    } as const
  )[stage]
}

function eventLabel(action: string) {
  const labels: Record<string, string> = {
    start_brief_generation: '开始生成设计说明',
    run_brief_generation: '生成设计说明',
    approve_brief_generation: '通过设计说明',
    edit_brief: '手动修改设计说明',
    start_image_prompt: '开始生成出图指令',
    run_image_prompt: '生成出图指令',
    approve_image_prompt: '通过出图指令',
    edit_prompt: '手动修改出图指令',
    start_image_generation: '开始生成候选图',
    run_image_generation: '生成候选图',
    approve_image_generation: '确认候选图',
    cancel_image_generation: '停止候选图生成',
    poll_image_generation: '检查候选图生成状态',
    set_current_version: '切换当前候选',
    rollback_step: '回到历史版本',
    fail_brief_generation: '设计说明生成失败',
    fail_image_prompt: '出图指令生成失败',
    fail_image_generation: '候选图生成失败',
  }
  return labels[action] ?? action.replace(/_/g, ' ')
}

function stageSummary(status: string) {
  const summaries: Record<string, { title: string; detail: string; tone: string }> = {
    draft: {
      title: '待开始',
      detail: '先生成设计说明',
      tone: 'border-outline-variant/18 bg-surface-container text-on-surface',
    },
    brief_generating: {
      title: '设计说明生成中',
      detail: '正在整理设计说明',
      tone: 'border-sky-400/25 bg-sky-400/10 text-sky-200',
    },
    brief_generated: {
      title: '待确认设计说明',
      detail: '确认后进入出图指令',
      tone: 'border-amber-400/25 bg-amber-400/10 text-amber-200',
    },
    brief_approved: {
      title: '可生成出图指令',
      detail: '设计说明已确认',
      tone: 'border-sky-400/25 bg-sky-400/10 text-sky-200',
    },
    prompt_generating: {
      title: '出图指令生成中',
      detail: '正在整理新的 prompt',
      tone: 'border-sky-400/25 bg-sky-400/10 text-sky-200',
    },
    prompt_generated: {
      title: '待确认出图指令',
      detail: '确认后开始生成候选图',
      tone: 'border-amber-400/25 bg-amber-400/10 text-amber-200',
    },
    prompt_approved: {
      title: '可生成候选图',
      detail: 'prompt 已确认',
      tone: 'border-sky-400/25 bg-sky-400/10 text-sky-200',
    },
    image_generating: {
      title: '候选图生成中',
      detail: '等待图片返回',
      tone: 'border-sky-400/25 bg-sky-400/10 text-sky-200',
    },
    image_generated: {
      title: '待选择候选图',
      detail: '选定当前候选后确认',
      tone: 'border-amber-400/25 bg-amber-400/10 text-amber-200',
    },
    completed: {
      title: '已完成',
      detail: '已确认最终候选图',
      tone: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-200',
    },
    failed: {
      title: '失败',
      detail: '查看日志后重试或回退',
      tone: 'border-error/25 bg-error/10 text-error',
    },
  }
  return (
    summaries[status] ?? {
      title: statusLabel(status),
      detail: '当前状态已更新。',
      tone: 'border-outline-variant/18 bg-surface-container text-on-surface',
    }
  )
}

function heroImage(url: string | null | undefined, alt: string) {
  if (!url) return null
  return (
    <div className="flex min-h-[420px] items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(107,135,255,0.2),_transparent_55%),linear-gradient(180deg,_#08101f_0%,_#050b16_100%)] px-4 py-6">
      <img src={url} alt={alt} className="max-h-[54vh] w-full object-contain drop-shadow-[0_18px_48px_rgba(0,0,0,0.38)]" />
    </div>
  )
}

function actionMeta(label: string | null) {
  const mapping: Record<string, { short: string; icon: string; tone: 'primary' | 'secondary' }> = {
    生成设计说明: { short: '生成', icon: 'auto_awesome', tone: 'primary' },
    通过设计说明: { short: '确认', icon: 'check_circle', tone: 'primary' },
    重新生成设计说明: { short: '重做', icon: 'refresh', tone: 'secondary' },
    生成出图指令: { short: '生成', icon: 'edit_note', tone: 'primary' },
    回到设计说明: { short: '回退', icon: 'undo', tone: 'secondary' },
    通过出图指令: { short: '确认', icon: 'check_circle', tone: 'primary' },
    重新生成出图指令: { short: '重做', icon: 'refresh', tone: 'secondary' },
    生成候选图: { short: '出图', icon: 'imagesmode', tone: 'primary' },
    回到出图指令: { short: '回退', icon: 'undo', tone: 'secondary' },
    检查生成状态: { short: '检查', icon: 'sync', tone: 'primary' },
    停止等待这些任务: { short: '停止', icon: 'stop_circle', tone: 'secondary' },
    通过当前候选图: { short: '确认', icon: 'check_circle', tone: 'primary' },
    再生成一张候选图: { short: '重做', icon: 'add_photo_alternate', tone: 'secondary' },
  }
  return label ? mapping[label] ?? { short: label, icon: 'bolt', tone: 'primary' } : null
}

function CandidateCard({
  version,
  isSelected,
  actionBusy,
  onSelect,
  onToggleStar,
}: {
  version: CandidateVersion
  isSelected: boolean
  actionBusy: boolean
  onSelect: () => void
  onToggleStar: () => void
}) {
  const firstImage = version.candidates[0]?.image_url
  const asyncStatus = version.async_job?.status
  const progress = Number(version.async_job?.progress ?? 0)

  return (
    <div
      className={clsx(
        'flex h-full flex-col overflow-hidden rounded-xl border bg-surface-container transition-all',
        isSelected
          ? 'border-primary/40 shadow-[0_12px_28px_rgba(0,0,0,0.22)]'
          : 'border-outline-variant/12 hover:border-primary/25',
      )}
    >
      <div className="grid min-h-[92px] grid-cols-[minmax(0,1fr)_auto] items-start gap-3 border-b border-outline-variant/10 px-3 py-3">
        <div className="min-w-0 pr-1">
          <p className="truncate text-xs font-bold text-on-surface">
            第 {Number(version.version.replace(/^v/, '')) || version.version} 次生成
          </p>
          <p className="mt-1 line-clamp-2 text-[11px] leading-5 text-on-surface-variant">
            {modelLabel(version.model)} · {formatRelativeDate(version.created_at)}
          </p>
        </div>
        <div className="flex shrink-0 items-start gap-2">
          {version.is_current ? (
            <span className="whitespace-nowrap rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">
              当前采用
            </span>
          ) : null}
          <button
            type="button"
            onClick={(event) => {
              event.stopPropagation()
              onToggleStar()
            }}
            title={version.is_starred ? '取消星标' : '加入星标'}
            className={clsx(
              'inline-flex h-8 w-8 items-center justify-center rounded-full border transition-colors',
              version.is_starred
                ? 'border-amber-400/35 bg-amber-400/12 text-amber-200'
                : 'border-outline-variant/16 bg-surface-container text-on-surface-variant hover:border-amber-400/25 hover:text-amber-200',
            )}
          >
            <Icon name="star" className="text-[16px]" />
          </button>
        </div>
      </div>
      {firstImage ? (
        <button
          type="button"
          onClick={onSelect}
          className="block w-full bg-[radial-gradient(circle_at_top,_rgba(107,135,255,0.18),_transparent_56%),linear-gradient(180deg,_#08101f_0%,_#050b16_100%)]"
        >
          <div className="flex aspect-square items-center justify-center px-3 py-3">
            <img src={firstImage} alt={version.version} className="max-h-full max-w-full object-contain" />
          </div>
        </button>
      ) : asyncStatus ? (
        <div className="flex aspect-square flex-col items-center justify-center gap-3 bg-primary/5">
          <Icon name="sync" className="animate-spin text-2xl text-primary-dim" />
          <div className="text-center">
            <p className="text-xs font-bold text-on-surface">
              {asyncStatus === 'queued' || asyncStatus === 'pending'
                ? '排队中'
                : asyncStatus === 'failed'
                  ? '生成失败'
                  : '生成中'}
            </p>
            <p className="mt-1 text-[11px] text-on-surface-variant">
              进度 {Number.isFinite(progress) ? progress : 0}%
            </p>
          </div>
        </div>
      ) : (
        <div className="flex aspect-square items-center justify-center bg-surface-container-lowest text-on-surface-variant">
          <Icon name="image" className="text-2xl" />
        </div>
      )}
      <div className="flex min-h-[66px] items-center justify-between gap-3 px-3 py-2">
        <div className="min-w-0 line-clamp-2 text-[11px] leading-5 text-on-surface-variant">
          {version.is_current ? '当前审批会使用这张图' : version.is_starred ? '已加入星标收藏' : '可星标，也可切成当前采用'}
        </div>
        <button
          type="button"
          disabled={actionBusy || version.is_current}
          onClick={onSelect}
          className="shrink-0 rounded-lg border border-outline-variant/18 px-2.5 py-1 text-[11px] font-bold text-on-surface transition-colors hover:bg-surface-container-highest disabled:cursor-not-allowed disabled:opacity-50"
        >
          {version.is_current ? '当前采用' : '设为当前'}
        </button>
      </div>
    </div>
  )
}

function BatchContextPanel({
  projectBackground,
  styleRequirements,
  onNavigate,
}: {
  projectBackground: string
  styleRequirements: string
  onNavigate: () => void
}) {
  return (
    <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold text-on-surface">批次继承上下文</p>
          <p className="mt-1 text-[11px] leading-5 text-on-surface-variant">
            这两部分由批次设定注入，会进入后续设计说明和出图 prompt。
          </p>
        </div>
        <button
          type="button"
          onClick={onNavigate}
          className="shrink-0 rounded-lg border border-outline-variant/14 px-2.5 py-1 text-[11px] font-semibold text-on-surface transition-colors hover:border-primary/25 hover:text-primary"
        >
          去批次设定修改
        </button>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs text-on-surface-variant">项目背景</p>
            <span className="rounded-full bg-surface-container-highest px-2 py-0.5 text-[10px] text-outline">
              跟随批次
            </span>
          </div>
          <p className="text-sm leading-7 text-on-surface/90">{projectBackground || '未填写'}</p>
        </div>
        <div>
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="text-xs text-on-surface-variant">统一风格要求</p>
            <span className="rounded-full bg-surface-container-highest px-2 py-0.5 text-[10px] text-outline">
              跟随批次
            </span>
          </div>
          <p className="whitespace-pre-wrap text-sm leading-7 text-on-surface/90">
            {styleRequirements || '未填写'}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function ItemWorkspace({
  item,
  task,
  globalSettings,
  workspace,
  actionBusy,
  pendingRunStep,
  actionError,
  taskName,
  onBackToDashboard,
  onUpdateItemInput,
  onEditBrief,
  onEditPrompt,
  onUpdateItemModel,
  onSelectVersion,
  onToggleCandidateStar,
  onRunStep,
  onApproveStep,
  onRollbackStep,
  onCancelImage,
}: {
  item: ItemSummary
  task: TaskSummary | null
  globalSettings: GlobalSettingsData | null
  workspace: WorkspacePayload
  actionBusy: boolean
  pendingRunStep: StageKey | null
  actionError: string | null
  taskName: string
  onBackToDashboard: () => void
  onUpdateItemInput: (payload: {
    title?: string | null
    category?: string | null
    description?: string | null
    extra_context?: string | null
    image_aspect_ratio?: string | null
    image_resolution?: string | null
  }) => Promise<void>
  onEditBrief: (payload: {
    title?: string | null
    description?: string | null
    visual_focus?: string | null
    keywords?: string[] | null
    note?: string | null
  }) => Promise<void>
  onEditPrompt: (payload: {
    prompt?: string | null
    negative_prompt?: string | null
    note?: string | null
  }) => Promise<void>
  onUpdateItemModel: (stage: StageKey, token: string) => Promise<void>
  onSelectVersion: (step: StageKey, version: string) => Promise<void>
  onToggleCandidateStar: (version: string, starred: boolean) => Promise<void>
  onRunStep: (step: StageKey) => void
  onApproveStep: (step: StageKey) => void
  onRollbackStep: (step: StageKey) => void
  onCancelImage: () => void
}) {
  const [outputTab, setOutputTab] = useState<OutputTab>('overview')
  const [inputEditing, setInputEditing] = useState(false)
  const [briefEditing, setBriefEditing] = useState(false)
  const [promptEditing, setPromptEditing] = useState(false)
  const [showStarredOnly, setShowStarredOnly] = useState(false)
  const [inputDraft, setInputDraft] = useState({
    title: '',
    category: '',
    description: '',
    extraContext: '',
    imageAspectRatio: '1:1',
    imageResolution: '1K',
  })
  const [briefDraft, setBriefDraft] = useState({
    title: '',
    visualFocus: '',
    description: '',
    keywords: '',
  })
  const [promptDraft, setPromptDraft] = useState({
    prompt: '',
    negativePrompt: '',
  })

  const briefOutput = outputRecord(workspace?.brief ?? null)
  const promptOutput = outputRecord(workspace?.prompt ?? null)
  const promptBatchContext = ((promptOutput.batch_context ?? {}) as Record<string, unknown>) || {}
  const candidateVersions = workspace?.candidate_pool.versions ?? []
  const approvedUrl = workspace?.candidate_pool.approved_image_url
  const selectedVersion =
    candidateVersions.find((v) => v.version === workspace.current_image_version) ??
    candidateVersions.find((v) => v.is_current) ??
    candidateVersions[0]
  const pendingVersions = candidateVersions.filter((v) => {
    const status = v.async_job?.status?.toLowerCase()
    return status && ['queued', 'pending', 'running', 'processing', 'in_progress'].includes(status)
  })
  const starredVersions = candidateVersions.filter((version) => version.is_starred)
  const candidateGridVersions =
    showStarredOnly && starredVersions.length > 0 ? starredVersions : candidateVersions
  const tagList = splitTags(item.category)
  const stageInfo = stageSummary(item.status)
  const taskProjectBackground = String(task?.project_background ?? '').trim()
  const taskStyleRequirements = String(task?.style_requirements ?? '').trim()
  const resolvedBriefProjectBackground = taskProjectBackground || String(briefOutput.project_background ?? '').trim()
  const resolvedBriefStyleRequirements = taskStyleRequirements || String(briefOutput.style_requirements ?? '').trim()
  const resolvedPromptProjectBackground =
    taskProjectBackground || String(promptBatchContext.project_background ?? '').trim()
  const resolvedPromptStyleRequirements =
    taskStyleRequirements || String(promptBatchContext.style_requirements ?? '').trim()
  const resolvedAspectRatio = item.runtime_overrides.image_aspect_ratio || task?.runtime_config?.image_aspect_ratio || '1:1'
  const resolvedResolution = item.runtime_overrides.image_resolution || task?.runtime_config?.image_resolution || '1K'
  const runtimeSource = {
    aspectRatio: item.runtime_overrides.image_aspect_ratio ? '条目覆盖' : '跟随批次',
    resolution: item.runtime_overrides.image_resolution ? '条目覆盖' : '跟随批次',
  }
  const recentEvents = workspace.events.slice().reverse().slice(0, 5)

  function resolveStageModel(stage: StageKey) {
    const itemOverride = item.model_overrides[stage]
    const taskOverride = task?.model_overrides?.[stage]
    const globalDefault = globalSettings?.defaults?.[stage]

    if (itemOverride.model || itemOverride.provider) {
      return {
        model: modelLabel(itemOverride.model || taskOverride?.model || globalDefault?.model || null),
        provider: itemOverride.provider || taskOverride?.provider || globalDefault?.provider || '未配置',
        source: '条目覆盖',
      }
    }
    if (taskOverride?.model || taskOverride?.provider) {
      return {
        model: modelLabel(taskOverride.model || globalDefault?.model || null),
        provider: taskOverride.provider || globalDefault?.provider || '未配置',
        source: '跟随批次',
      }
    }
    return {
      model: modelLabel(globalDefault?.model || null),
      provider: globalDefault?.provider || '未配置',
      source: '跟随全局',
    }
  }

  function stageForModelPicker(status: string): StageKey {
    if (status === 'draft' || status === 'brief_generating' || status === 'brief_generated') {
      return 'brief_generation'
    }
    if (status === 'brief_approved' || status === 'prompt_generating' || status === 'prompt_generated') {
      return 'image_prompt'
    }
    return 'image_generation'
  }

  const editableStage = stageForModelPicker(workspace.status)
  const effectiveStageModel = resolveStageModel(editableStage)
  const currentStageOverride = item.model_overrides[editableStage]
  const currentStageModelToken =
    currentStageOverride.provider && currentStageOverride.model
      ? `${currentStageOverride.provider}::${currentStageOverride.model}`
      : '__inherit__'
  const stageModelOptions = (globalSettings?.providers ?? []).flatMap((provider) =>
    provider.models
      .filter((model) => model.stages.includes(editableStage))
      .map((model) => ({
        token: `${provider.id}::${model.id}`,
        label: `${provider.label} · ${model.label}`,
      })),
  )

  function openBriefEditor() {
    setBriefDraft({
      title: String(briefOutput.title ?? item.title),
      visualFocus: String(briefOutput.visual_focus ?? ''),
      description: String(briefOutput.description ?? item.description),
      keywords: stringList(briefOutput.keywords).join('、'),
    })
    setBriefEditing(true)
  }

  function openInputEditor() {
    setInputDraft({
      title: String(item.title ?? ''),
      category: String(item.category ?? ''),
      description: String(item.description ?? ''),
      extraContext: String(item.extra_context ?? ''),
      imageAspectRatio: resolvedAspectRatio,
      imageResolution: resolvedResolution,
    })
    setInputEditing(true)
  }

  function openPromptEditor() {
    setPromptDraft({
      prompt: String(promptOutput.prompt ?? ''),
      negativePrompt: String(promptOutput.negative_prompt ?? ''),
    })
    setPromptEditing(true)
  }

  function stageActionBar() {
    switch (workspace.status) {
      case 'draft':
        return {
          primaryLabel: '生成设计说明',
          primaryAction: () => onRunStep('brief_generation'),
          secondaryLabel: null,
          secondaryAction: null,
        }
      case 'brief_generating':
        return {
          primaryLabel: null,
          primaryAction: null,
          secondaryLabel: null,
          secondaryAction: null,
        }
      case 'brief_generated':
        return {
          primaryLabel: '通过设计说明',
          primaryAction: () => onApproveStep('brief_generation'),
          secondaryLabel: '重新生成设计说明',
          secondaryAction: () => onRunStep('brief_generation'),
        }
      case 'brief_approved':
        return {
          primaryLabel: '生成出图指令',
          primaryAction: () => onRunStep('image_prompt'),
          secondaryLabel: '回到设计说明',
          secondaryAction: () => onRollbackStep('brief_generation'),
        }
      case 'prompt_generating':
        return {
          primaryLabel: null,
          primaryAction: null,
          secondaryLabel: null,
          secondaryAction: null,
        }
      case 'prompt_generated':
        return {
          primaryLabel: '通过出图指令',
          primaryAction: () => onApproveStep('image_prompt'),
          secondaryLabel: '重新生成出图指令',
          secondaryAction: () => onRunStep('image_prompt'),
        }
      case 'prompt_approved':
        return {
          primaryLabel: '生成候选图',
          primaryAction: () => onRunStep('image_generation'),
          secondaryLabel: '回到出图指令',
          secondaryAction: () => onRollbackStep('image_prompt'),
        }
      case 'image_generating':
        return {
          primaryLabel: '再生成一张候选图',
          primaryAction: () => onRunStep('image_generation'),
          secondaryLabel: '停止等待这些任务',
          secondaryAction: () => onCancelImage(),
        }
      case 'image_generated':
        return {
          primaryLabel: '通过当前候选图',
          primaryAction: () => onApproveStep('image_generation'),
          secondaryLabel: '再生成一张候选图',
          secondaryAction: () => onRunStep('image_generation'),
        }
      case 'failed':
        return {
          primaryLabel: '再生成一张候选图',
          primaryAction: () => onRunStep('image_generation'),
          secondaryLabel: '回到出图指令',
          secondaryAction: () => onRollbackStep('image_prompt'),
        }
      case 'completed':
        return {
          primaryLabel: '再生成一张候选图',
          primaryAction: () => onRunStep('image_generation'),
          secondaryLabel: '回到出图指令',
          secondaryAction: () => onRollbackStep('image_prompt'),
        }
      default:
        return {
          primaryLabel: null,
          primaryAction: null,
          secondaryLabel: null,
          secondaryAction: null,
        }
    }
  }

  const actionBar = stageActionBar()
  const primaryActionMeta = actionMeta(actionBar.primaryLabel)
  const secondaryActionMeta = actionMeta(actionBar.secondaryLabel)
  const pendingGenerationCount = pendingVersions.length
  const starredCount = starredVersions.length
  const selectedImageUrl = approvedUrl || selectedVersion?.candidates[0]?.image_url || ''
  const promptGenerating =
    workspace.status === 'prompt_generating' || (actionBusy && pendingRunStep === 'image_prompt')
  const briefGenerating =
    workspace.status === 'brief_generating' || (actionBusy && pendingRunStep === 'brief_generation')
  const stageTitle =
    promptGenerating
      ? '出图指令生成中'
      : briefGenerating
        ? '设计说明生成中'
        : pendingGenerationCount > 0
      ? `后台生成中${pendingGenerationCount > 1 ? ` · ${pendingGenerationCount} 个任务` : ''}`
      : stageInfo.title
  const stageDetail =
    promptGenerating
      ? '正在基于设计说明整理 prompt，稍后会自动进入下一步。'
      : briefGenerating
        ? '正在整理设计说明，请稍候。'
        : pendingGenerationCount > 0
      ? '后台还有候选图在生成，你可以继续追加重做，也可以先挑已有结果。'
      : stageInfo.detail

  const tabs = [
    ['overview', '总览'],
    ['brief', '设计说明'],
    ['prompt', '出图指令'],
    ['candidate', '候选池'],
  ] as const

  function openImagePreview(url: string | null | undefined) {
    if (!url) return
    window.open(url, '_blank', 'noopener,noreferrer')
  }

  function downloadImage(url: string | null | undefined, filename: string) {
    if (!url) return
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    anchor.target = '_blank'
    anchor.rel = 'noopener noreferrer'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  }

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-surface">
      <div className="shrink-0 border-b border-outline-variant/10 bg-surface-container-low/92 px-4 py-3 backdrop-blur-xl">
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={onBackToDashboard}
            className="inline-flex items-center gap-2 rounded-lg border border-outline-variant/14 bg-surface-container px-3 py-1.5 text-xs font-semibold text-on-surface transition-colors hover:border-primary/25 hover:text-primary"
          >
            <Icon name="arrow_back" className="text-[16px]" />
            返回批次
          </button>
          <div className="min-w-0 text-right">
            <div className="truncate text-[11px] uppercase tracking-[0.16em] text-outline">
              {taskName || '当前批次'}
            </div>
            <div className="truncate text-sm font-bold text-on-surface">{item.title}</div>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-3 overflow-hidden p-3">
        <section className="flex min-h-0 w-64 flex-col gap-3 overflow-y-auto pr-1">
          <div className="rounded-xl bg-surface-container-low p-4">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-on-surface">原始输入</h3>
                <p className="mt-1 text-xs text-on-surface-variant">这是用户最初给这条 item 的信息。</p>
              </div>
              <button
                type="button"
                onClick={openInputEditor}
                className="rounded-lg border border-outline-variant/16 px-3 py-1.5 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container"
              >
                编辑
              </button>
            </div>
            {inputEditing ? (
              <form
                className="space-y-4"
                onSubmit={async (event) => {
                  event.preventDefault()
                  await onUpdateItemInput({
                    title: inputDraft.title,
                    category: inputDraft.category,
                    description: inputDraft.description,
                    extra_context: inputDraft.extraContext,
                    image_aspect_ratio: inputDraft.imageAspectRatio,
                    image_resolution: inputDraft.imageResolution,
                  })
                  setInputEditing(false)
                }}
              >
                <label className="block">
                  <span className="mb-1.5 block text-xs text-on-surface-variant">条目名称</span>
                  <input
                    value={inputDraft.title}
                    onChange={(event) => setInputDraft((current) => ({ ...current, title: event.target.value }))}
                    className="w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs text-on-surface-variant">标签</span>
                  <input
                    value={inputDraft.category}
                    onChange={(event) => setInputDraft((current) => ({ ...current, category: event.target.value }))}
                    className="w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                    placeholder="可用逗号、顿号或斜杠分隔多个标签"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs text-on-surface-variant">描述</span>
                  <textarea
                    value={inputDraft.description}
                    onChange={(event) =>
                      setInputDraft((current) => ({ ...current, description: event.target.value }))
                    }
                    className="min-h-24 w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm leading-6 text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-xs text-on-surface-variant">补充说明</span>
                  <textarea
                    value={inputDraft.extraContext}
                    onChange={(event) =>
                      setInputDraft((current) => ({ ...current, extraContext: event.target.value }))
                    }
                    className="min-h-20 w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm leading-6 text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  />
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block">
                    <span className="mb-1.5 block text-xs text-on-surface-variant">宽高比</span>
                    <select
                      value={inputDraft.imageAspectRatio}
                      onChange={(event) =>
                        setInputDraft((current) => ({ ...current, imageAspectRatio: event.target.value }))
                      }
                      className="w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                    >
                      {IMAGE_ASPECT_RATIO_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    <span className="mb-1.5 block text-xs text-on-surface-variant">分辨率</span>
                    <select
                      value={inputDraft.imageResolution}
                      onChange={(event) =>
                        setInputDraft((current) => ({ ...current, imageResolution: event.target.value }))
                      }
                      className="w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                    >
                      {IMAGE_RESOLUTION_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setInputEditing(false)}
                    className="rounded-lg px-3 py-2 text-xs font-medium text-on-surface-variant transition-colors hover:bg-surface-container"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={actionBusy}
                    className="rounded-lg bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {actionBusy ? '保存中…' : '保存原始输入'}
                  </button>
                </div>
              </form>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="mb-1 block text-[11px] uppercase tracking-[0.14em] text-on-surface-variant">
                    条目名称
                  </label>
                  <p className="text-lg font-bold text-on-surface">{item.title}</p>
                </div>

                {tagList.length > 0 ? (
                  <div>
                    <label className="mb-1 block text-[11px] uppercase tracking-[0.14em] text-on-surface-variant">
                      标签
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                      {tagList.map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex rounded-full bg-secondary-container px-2 py-0.5 text-[11px] font-bold text-on-secondary-container"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}

                <div>
                  <label className="mb-1 block text-[11px] uppercase tracking-[0.14em] text-on-surface-variant">
                    描述
                  </label>
                  <p className="text-sm leading-6 text-on-surface">{item.description || '未填写'}</p>
                </div>

                {item.extra_context ? (
                  <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
                    <label className="mb-1 block text-[11px] uppercase tracking-[0.14em] text-on-surface-variant">
                      补充说明
                    </label>
                    <p className="text-sm leading-6 text-on-surface-variant">{item.extra_context}</p>
                  </div>
                ) : null}

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-outline-variant/15 bg-surface-container p-3">
                    <p className="mb-1 text-[11px] text-on-surface-variant">宽高比</p>
                    <p className="text-sm font-semibold text-on-surface">{resolvedAspectRatio}</p>
                    <p className="mt-1 text-[11px] text-outline">{runtimeSource.aspectRatio}</p>
                  </div>
                  <div className="rounded-xl border border-outline-variant/15 bg-surface-container p-3">
                    <p className="mb-1 text-[11px] text-on-surface-variant">分辨率</p>
                    <p className="text-sm font-semibold text-on-surface">{resolvedResolution}</p>
                    <p className="mt-1 text-[11px] text-outline">{runtimeSource.resolution}</p>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl bg-surface-container-low p-4">
            <h3 className="mb-4 text-sm font-bold text-on-surface">当前模型</h3>
            <div className="space-y-2">
              {(
                [
                  ['设计说明', 'brief_generation'],
                  ['出图指令', 'image_prompt'],
                  ['候选图', 'image_generation'],
                ] as const
              ).map(([label, stage]) => {
                const resolved = resolveStageModel(stage)
                return (
                  <div
                    key={label}
                    className="rounded-xl border border-outline-variant/12 bg-surface-container p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-[11px] text-on-surface-variant">{label}</p>
                      <span className="rounded-full bg-surface-container-highest px-2 py-0.5 text-[10px] text-outline">
                        {resolved.source}
                      </span>
                    </div>
                    <p className="mt-1 text-sm font-semibold text-on-surface">{resolved.model}</p>
                    <p className="mt-1 text-[11px] text-on-surface-variant">{resolved.provider}</p>
                  </div>
                )
              })}
            </div>
          </div>

          <div className="rounded-xl bg-surface-container-low p-4">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="text-sm font-bold text-on-surface">最近动态</h3>
              <span className="text-[11px] text-outline">最近 5 条</span>
            </div>
            <div className="space-y-2">
              {recentEvents.length === 0 ? (
                <p className="text-xs text-on-surface-variant">暂无动态</p>
              ) : (
                recentEvents.map((event, i) => (
                  <div
                    key={`${String(event.timestamp ?? '')}-${i}`}
                    className="rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-2.5"
                  >
                    <p className="text-xs font-semibold text-on-surface">
                      {eventLabel(String(event.action ?? 'unknown'))}
                    </p>
                    <p className="mt-1 text-[11px] text-on-surface-variant">
                      {formatRelativeDate(String(event.timestamp ?? ''))}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>

        <section className="flex min-h-0 flex-1 flex-col gap-3 overflow-hidden">
          <div className="flex w-fit items-center gap-1 rounded-xl bg-surface-container-low p-1">
            {tabs.map(([value, label]) => (
              <button
                key={value}
                onClick={() => setOutputTab(value)}
                className={clsx(
                  'rounded-lg px-4 py-1.5 text-sm font-medium transition-colors',
                  outputTab === value
                    ? 'bg-surface-container-highest text-primary'
                    : 'text-on-surface-variant hover:text-on-surface',
                )}
              >
                {label}
              </button>
            ))}
          </div>

          <div className="flex-1 space-y-3 overflow-y-auto pr-1">
            {outputTab === 'overview' && (
              <>
                <div className="group relative overflow-hidden rounded-xl bg-surface-container-lowest ring-1 ring-outline-variant/8">
                  <div className="absolute left-4 top-4 z-10">
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-primary px-2.5 py-1 text-[11px] font-bold text-on-primary-fixed">
                        {approvedUrl ? '当前采用' : '当前候选'}
                      </span>
                      {selectedVersion?.is_starred ? (
                        <span className="rounded-full bg-amber-400/12 px-2 py-0.5 text-[11px] font-bold text-amber-200">
                          已星标
                        </span>
                      ) : null}
                    </div>
                  </div>
                  {approvedUrl || selectedVersion?.candidates[0]?.image_url ? (
                    heroImage(approvedUrl || selectedVersion?.candidates[0]?.image_url || '', item.title)
                  ) : (
                    <div className="flex min-h-[420px] flex-col items-center justify-center bg-surface-container-lowest">
                      <Icon name="image" className="mb-3 text-4xl text-outline" />
                      <p className="text-sm text-on-surface-variant">还没有候选图</p>
                    </div>
                  )}
                  {(approvedUrl || selectedVersion) && (
                    <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-surface-container-lowest via-surface-container-lowest/82 to-transparent p-4">
                      <div className="flex items-end justify-between gap-4">
                        <div>
                          <p className="text-[11px] text-on-surface-variant">
                            {approvedUrl ? '当前确认结果' : '当前候选版本'}
                          </p>
                          <h4 className="text-base font-bold text-on-surface">
                            {selectedVersion?.version
                              ? `V${selectedVersion.version.replace(/^v/, '')} 候选`
                              : '已确认'}
                          </h4>
                        </div>
                        <div className="flex gap-2">
                          {selectedVersion ? (
                            <button
                              type="button"
                              title={selectedVersion.is_starred ? '取消星标' : '加入星标'}
                              onClick={() =>
                                void onToggleCandidateStar(selectedVersion.version, !selectedVersion.is_starred)
                              }
                              className={clsx(
                                'rounded-lg border p-2 backdrop-blur-md transition-colors',
                                selectedVersion.is_starred
                                  ? 'border-amber-400/30 bg-amber-400/12 text-amber-200'
                                  : 'border-outline-variant/20 bg-surface-bright/20 hover:bg-surface-bright/40',
                              )}
                            >
                              <Icon name="star" className="text-sm" />
                            </button>
                          ) : null}
                          <button
                            type="button"
                            title="打开大图"
                            onClick={() => openImagePreview(selectedImageUrl)}
                            className="rounded-lg border border-outline-variant/20 bg-surface-bright/20 p-2 backdrop-blur-md hover:bg-surface-bright/40"
                          >
                            <Icon name="fullscreen" className="text-sm" />
                          </button>
                          <button
                            type="button"
                            title="下载当前图片"
                            onClick={() =>
                              downloadImage(
                                selectedImageUrl,
                                `${item.item_id || 'item'}-${selectedVersion?.version || 'current'}.png`,
                              )
                            }
                            className="rounded-lg border border-outline-variant/20 bg-surface-bright/20 p-2 backdrop-blur-md hover:bg-surface-bright/40"
                          >
                            <Icon name="download" className="text-sm" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {pendingVersions.length > 0 ? (
                  <div className="grid grid-cols-3 gap-4">
                    {pendingVersions.slice(0, 3).map((version) => (
                      <div
                        key={version.version}
                        className="relative flex aspect-[4/3] flex-col items-center justify-center overflow-hidden rounded-xl border-2 border-dashed border-outline-variant/20 bg-surface-container-low"
                      >
                        <div className="absolute inset-0 animate-pulse bg-primary/5" />
                        <Icon name="sync" className="animate-spin text-3xl text-primary-dim" />
                        <span className="mt-2 text-xs font-bold text-on-surface">
                          第 {Number(version.version.replace(/^v/, '')) || version.version} 次生成中
                        </span>
                        <span className="mt-1 text-[11px] text-on-surface-variant">
                          进度 {version.async_job?.progress ?? 0}%
                        </span>
                      </div>
                    ))}
                  </div>
                ) : null}

                <div className="rounded-xl bg-surface-container-low p-4 ring-1 ring-outline-variant/8">
                  <div className="mb-3 flex items-center gap-2">
                    <Icon name="architecture" className="text-base text-primary" />
                    <h3 className="text-sm font-bold text-on-surface">设计说明摘要</h3>
                  </div>
                  <div className="grid gap-3 lg:grid-cols-[14rem_minmax(0,1fr)]">
                    <div className="rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3">
                      <div className="text-[11px] text-on-surface-variant">名称</div>
                      <div className="mt-1 text-base font-semibold text-on-surface">
                        {String(briefOutput.title ?? item.title)}
                      </div>
                    </div>
                    <div className="rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3">
                      <div className="text-[11px] text-on-surface-variant">视觉重点</div>
                      <div className="mt-1 text-sm font-semibold leading-6 text-on-surface">
                        {String(briefOutput.visual_focus ?? '暂无')}
                      </div>
                    </div>
                    <div className="lg:col-span-2 rounded-xl border border-outline-variant/10 bg-surface-container px-3 py-3">
                      <div className="mb-2 text-[11px] text-on-surface-variant">关键词</div>
                      <div className="flex flex-wrap gap-1.5">
                        {stringList(briefOutput.keywords).length > 0 ? (
                          stringList(briefOutput.keywords).map((kw) => (
                            <span
                              key={kw}
                              className="h-fit rounded-full border border-primary/10 bg-surface-container-highest px-2 py-0.5 text-[11px] text-primary-fixed"
                            >
                              {kw}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-on-surface-variant">暂无关键词</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </>
            )}

            {outputTab === 'brief' && (
              <div className="rounded-xl bg-surface-container-low p-5 ring-1 ring-outline-variant/8">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <h4 className="text-xl font-bold text-on-surface">设计说明</h4>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      {workspace.brief
                        ? `${workspace.brief.version} · ${modelLabel(workspace.brief.model)}`
                        : '当前还没有设计说明'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {workspace.brief ? (
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-bold text-primary">
                        已生成
                      </span>
                    ) : null}
                    <button
                      type="button"
                      onClick={openBriefEditor}
                      className="rounded-lg border border-outline-variant/16 px-3 py-1.5 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container"
                    >
                      编辑
                    </button>
                  </div>
                </div>

                {briefEditing ? (
                  <form
                    className="space-y-4"
                    onSubmit={async (event) => {
                      event.preventDefault()
                      await onEditBrief({
                        title: briefDraft.title,
                        description: briefDraft.description,
                        visual_focus: briefDraft.visualFocus,
                        keywords: splitTags(briefDraft.keywords),
                      })
                      setBriefEditing(false)
                    }}
                  >
                    <div className="grid gap-4 md:grid-cols-2">
                      <label className="block">
                        <span className="mb-1.5 block text-xs text-on-surface-variant">名称</span>
                        <input
                          value={briefDraft.title}
                          onChange={(event) =>
                            setBriefDraft((current) => ({ ...current, title: event.target.value }))
                          }
                          className="w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                        />
                      </label>
                      <label className="block">
                        <span className="mb-1.5 block text-xs text-on-surface-variant">视觉重点</span>
                        <input
                          value={briefDraft.visualFocus}
                          onChange={(event) =>
                            setBriefDraft((current) => ({ ...current, visualFocus: event.target.value }))
                          }
                          className="w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                        />
                      </label>
                    </div>
                    <label className="block">
                      <span className="mb-1.5 block text-xs text-on-surface-variant">需求整理</span>
                      <textarea
                        value={briefDraft.description}
                        onChange={(event) =>
                          setBriefDraft((current) => ({ ...current, description: event.target.value }))
                        }
                        className="min-h-28 w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm leading-6 text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1.5 block text-xs text-on-surface-variant">关键词</span>
                      <input
                        value={briefDraft.keywords}
                        onChange={(event) =>
                          setBriefDraft((current) => ({ ...current, keywords: event.target.value }))
                        }
                        className="w-full rounded-xl bg-surface-container-highest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                        placeholder="用逗号、顿号或斜杠分隔"
                      />
                    </label>
                    <BatchContextPanel
                      projectBackground={resolvedBriefProjectBackground}
                      styleRequirements={resolvedBriefStyleRequirements}
                      onNavigate={onBackToDashboard}
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setBriefEditing(false)}
                        className="rounded-lg px-3 py-2 text-xs font-medium text-on-surface-variant transition-colors hover:bg-surface-container"
                      >
                        取消
                      </button>
                      <button
                        type="submit"
                        disabled={actionBusy}
                        className="rounded-lg bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {actionBusy ? '保存中…' : '保存设计说明'}
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                        <p className="mb-2 text-xs text-on-surface-variant">名称</p>
                        <p className="text-sm font-semibold text-on-surface">
                          {String(briefOutput.title ?? item.title)}
                        </p>
                      </div>
                      <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                        <p className="mb-2 text-xs text-on-surface-variant">视觉重点</p>
                        <p className="text-sm font-semibold text-on-surface">
                          {String(briefOutput.visual_focus ?? '暂无')}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                      <p className="mb-2 text-xs text-on-surface-variant">需求整理</p>
                      <p className="text-sm leading-7 text-on-surface/90">
                        {String(briefOutput.description ?? '暂无设计说明')}
                      </p>
                    </div>
                    <div className="mt-4 rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                      <p className="mb-2 text-xs text-on-surface-variant">关键词</p>
                      <p className="text-sm leading-7 text-on-surface/90">
                        {stringList(briefOutput.keywords).join(' · ') || '暂无'}
                      </p>
                    </div>
                    <div className="mt-4">
                      <BatchContextPanel
                        projectBackground={resolvedBriefProjectBackground}
                        styleRequirements={resolvedBriefStyleRequirements}
                        onNavigate={onBackToDashboard}
                      />
                    </div>
                  </>
                )}
              </div>
            )}

            {outputTab === 'prompt' && (
              <div className="rounded-xl bg-surface-container-low p-5 ring-1 ring-outline-variant/8">
                <div className="mb-4 flex items-start justify-between gap-3">
                  <div>
                    <h4 className="text-xl font-bold text-on-surface">出图指令</h4>
                    <p className="mt-1 text-sm text-on-surface-variant">
                      {promptGenerating
                        ? '正在生成新的出图指令…'
                        : workspace.prompt
                        ? `${workspace.prompt.version} · ${modelLabel(workspace.prompt.model)}`
                        : '当前还没有出图指令'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {workspace.prompt ? (
                      <span className="rounded-full bg-secondary-container px-2 py-0.5 text-[11px] font-bold text-on-secondary-container">
                        已生成
                      </span>
                    ) : null}
                    <button
                      type="button"
                      onClick={openPromptEditor}
                      className="rounded-lg border border-outline-variant/16 px-3 py-1.5 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container"
                    >
                      编辑
                    </button>
                  </div>
                </div>

                {promptEditing ? (
                  <form
                    className="space-y-4"
                    onSubmit={async (event) => {
                      event.preventDefault()
                      await onEditPrompt({
                        prompt: promptDraft.prompt,
                        negative_prompt: promptDraft.negativePrompt,
                      })
                      setPromptEditing(false)
                    }}
                  >
                    <label className="block">
                      <span className="mb-1.5 block text-xs text-on-surface-variant">Prompt</span>
                      <textarea
                        value={promptDraft.prompt}
                        onChange={(event) =>
                          setPromptDraft((current) => ({ ...current, prompt: event.target.value }))
                        }
                        className="min-h-28 w-full rounded-xl bg-surface-container-highest px-3 py-2 font-mono text-sm leading-7 text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                      />
                    </label>
                    <label className="block">
                      <span className="mb-1.5 block text-xs text-on-surface-variant">Negative Prompt</span>
                      <textarea
                        value={promptDraft.negativePrompt}
                        onChange={(event) =>
                          setPromptDraft((current) => ({ ...current, negativePrompt: event.target.value }))
                        }
                        className="min-h-28 w-full rounded-xl bg-surface-container-highest px-3 py-2 font-mono text-sm leading-7 text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                      />
                    </label>
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setPromptEditing(false)}
                        className="rounded-lg px-3 py-2 text-xs font-medium text-on-surface-variant transition-colors hover:bg-surface-container"
                      >
                        取消
                      </button>
                      <button
                        type="submit"
                        disabled={actionBusy}
                        className="rounded-lg bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {actionBusy ? '保存中…' : '保存出图指令'}
                      </button>
                    </div>
                  </form>
                ) : (
                  <div className="space-y-4">
                    {promptGenerating && !workspace.prompt ? (
                      <div className="flex min-h-40 flex-col items-center justify-center rounded-xl border border-dashed border-primary/25 bg-primary/5">
                        <Icon name="progress_activity" className="animate-spin text-3xl text-primary" />
                        <p className="mt-3 text-sm font-semibold text-on-surface">正在生成出图指令</p>
                        <p className="mt-1 text-xs text-on-surface-variant">
                          模型会结合设计说明和批次上下文整理新的 prompt。
                        </p>
                      </div>
                    ) : null}
                    <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                      <p className="mb-2 flex items-center gap-2 text-xs text-on-surface-variant">
                        <Icon name="terminal" className="text-sm" />
                        Prompt
                      </p>
                      <p className="font-mono text-sm leading-7 text-on-surface/90">
                        {String(promptOutput.prompt ?? '暂无出图指令')}
                      </p>
                    </div>
                    <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                      <p className="mb-2 text-xs text-on-surface-variant">Negative Prompt</p>
                      <p className="font-mono text-sm leading-7 text-on-surface/90">
                        {String(promptOutput.negative_prompt ?? '暂无')}
                      </p>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                        <p className="mb-2 text-xs text-on-surface-variant">来源设计说明</p>
                        <p className="text-sm font-semibold text-on-surface">
                          {String(inputRecord(workspace.prompt).brief_version ?? '暂无')}
                        </p>
                      </div>
                      <div className="rounded-xl border border-outline-variant/10 bg-surface-container p-4">
                        <p className="mb-2 text-xs text-on-surface-variant">当前模型</p>
                        <p className="text-sm font-semibold text-on-surface">
                          {modelLabel(workspace.prompt?.model)}
                        </p>
                      </div>
                    </div>
                    <BatchContextPanel
                      projectBackground={resolvedPromptProjectBackground}
                      styleRequirements={resolvedPromptStyleRequirements}
                      onNavigate={onBackToDashboard}
                    />
                  </div>
                )}
              </div>
            )}

            {outputTab === 'candidate' && (
              <div className="space-y-4">
                <div className="relative overflow-hidden rounded-xl bg-surface-container-low ring-1 ring-outline-variant/8">
                  <div className="flex items-center justify-between gap-3 border-b border-outline-variant/10 px-4 py-3">
                    <div>
                      <h4 className="text-base font-bold text-on-surface">当前采用</h4>
                      <p className="mt-1 text-xs text-on-surface-variant">
                        星标可以多选收藏，真正推进流程的仍然只有一张当前采用图。
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full bg-amber-400/12 px-2 py-0.5 text-[11px] font-bold text-amber-200">
                        已星标 {starredCount}
                      </span>
                      <span
                        className={clsx(
                          'rounded-full px-2 py-0.5 text-[11px] font-bold',
                          item.status === 'completed'
                            ? 'bg-emerald-400/10 text-emerald-300'
                            : 'bg-primary/10 text-primary',
                        )}
                      >
                        {statusLabel(item.status)}
                      </span>
                    </div>
                  </div>
                  {selectedVersion?.candidates[0]?.image_url
                    ? heroImage(selectedVersion.candidates[0].image_url, selectedVersion.version)
                    : (
                      <div className="flex min-h-[420px] items-center justify-center rounded border border-dashed border-primary/25 bg-primary/5 text-on-surface-variant">
                        尚未选择当前候选图
                      </div>
                    )}
                  {selectedVersion?.candidates[0]?.image_url ? (
                    <div className="absolute bottom-4 right-4 flex gap-2">
                      <button
                        type="button"
                        title={selectedVersion.is_starred ? '取消星标' : '加入星标'}
                        onClick={() =>
                          void onToggleCandidateStar(selectedVersion.version, !selectedVersion.is_starred)
                        }
                        className={clsx(
                          'rounded-lg border p-2 backdrop-blur-md transition-colors',
                          selectedVersion.is_starred
                            ? 'border-amber-400/30 bg-amber-400/12 text-amber-200'
                            : 'border-outline-variant/20 bg-surface-bright/20 hover:bg-surface-bright/40',
                        )}
                      >
                        <Icon name="star" className="text-sm" />
                      </button>
                      <button
                        type="button"
                        title="打开大图"
                        onClick={() => openImagePreview(selectedVersion.candidates[0]?.image_url)}
                        className="rounded-lg border border-outline-variant/20 bg-surface-bright/20 p-2 backdrop-blur-md hover:bg-surface-bright/40"
                      >
                        <Icon name="fullscreen" className="text-sm" />
                      </button>
                      <button
                        type="button"
                        title="下载当前图片"
                        onClick={() =>
                          downloadImage(
                            selectedVersion.candidates[0]?.image_url,
                            `${item.item_id || 'item'}-${selectedVersion.version || 'current'}.png`,
                          )
                        }
                        className="rounded-lg border border-outline-variant/20 bg-surface-bright/20 p-2 backdrop-blur-md hover:bg-surface-bright/40"
                      >
                        <Icon name="download" className="text-sm" />
                      </button>
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-surface-container-low px-4 py-3 ring-1 ring-outline-variant/8">
                  <div className="flex items-center gap-2 text-xs text-on-surface-variant">
                    <span>候选 {candidateVersions.length} 张</span>
                    <span className="text-outline">·</span>
                    <span>星标 {starredCount} 张</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setShowStarredOnly(false)}
                      className={clsx(
                        'rounded-lg px-2.5 py-1 text-xs font-medium transition-colors',
                        !showStarredOnly
                          ? 'bg-surface-container-highest text-primary'
                          : 'text-on-surface-variant hover:text-on-surface',
                      )}
                    >
                      全部候选
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowStarredOnly(true)}
                      className={clsx(
                        'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors',
                        showStarredOnly
                          ? 'bg-surface-container-highest text-amber-200'
                          : 'text-on-surface-variant hover:text-on-surface',
                      )}
                    >
                      <Icon name="star" className="text-[13px]" />
                      只看星标
                    </button>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                  {candidateGridVersions.length === 0 ? (
                    <div className="col-span-full rounded-xl border border-dashed border-outline-variant/20 bg-surface-container-high p-6 text-center text-sm text-on-surface-variant">
                      {showStarredOnly ? '还没有星标候选图' : '当前还没有候选池内容'}
                    </div>
                  ) : (
                    candidateGridVersions.map((version) => (
                      <CandidateCard
                        key={version.version}
                        version={version}
                        isSelected={version.version === selectedVersion?.version}
                        actionBusy={actionBusy}
                        onSelect={() => void onSelectVersion('image_generation', version.version)}
                        onToggleStar={() => void onToggleCandidateStar(version.version, !version.is_starred)}
                      />
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-xl bg-surface-container-low px-4 py-2.5 ring-1 ring-outline-variant/8">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div className="min-w-0 flex items-start gap-3">
                <span
                  className={clsx(
                    'inline-flex rounded-full border px-2 py-0.5 text-[11px] font-bold',
                    stageInfo.tone,
                  )}
                >
                  {stageTitle}
                </span>
                <div className="min-w-0">
                  <div className="text-[11px] leading-5 text-on-surface-variant">{stageDetail}</div>
                </div>
                {actionError ? (
                  <span className="rounded-lg bg-error-container px-2 py-1 text-xs text-on-error-container">
                    {actionError}
                  </span>
                ) : null}
              </div>
              <div className="flex flex-wrap items-center justify-end gap-2">
                <div className="min-w-[16rem] rounded-lg border border-outline-variant/12 bg-surface-container px-2.5 py-2">
                  <div className="mb-1 flex items-center justify-between gap-2">
                    <span className="text-[10px] uppercase tracking-[0.14em] text-on-surface-variant">
                      本步模型
                    </span>
                    <span className="text-[10px] text-outline">{stageLabel(editableStage)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={currentStageModelToken}
                      disabled={actionBusy || stageModelOptions.length === 0}
                      onChange={(event) => void onUpdateItemModel(editableStage, event.target.value)}
                      className="min-w-0 flex-1 rounded-md border border-outline-variant/12 bg-surface-container-highest px-2 py-1.5 text-xs text-on-surface outline-none transition-colors focus:border-primary/35"
                    >
                      <option value="__inherit__">
                        跟随当前默认 · {effectiveStageModel.model}
                      </option>
                      {stageModelOptions.map((option) => (
                        <option key={option.token} value={option.token}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <span className="shrink-0 rounded-full bg-surface-container-highest px-2 py-0.5 text-[10px] text-outline">
                      {effectiveStageModel.source}
                    </span>
                  </div>
                </div>
                {actionBar.secondaryLabel && secondaryActionMeta ? (
                  <button
                    disabled={actionBusy}
                    onClick={actionBar.secondaryAction ?? undefined}
                    title={actionBar.secondaryLabel}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-surface-container-highest px-2.5 py-1.5 text-[11px] font-semibold text-on-surface transition-colors hover:bg-surface-bright disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Icon name={secondaryActionMeta.icon} className="text-[15px]" />
                    {secondaryActionMeta.short}
                  </button>
                ) : null}
                {actionBar.primaryLabel && primaryActionMeta ? (
                  <button
                    disabled={actionBusy}
                    onClick={actionBar.primaryAction ?? undefined}
                    title={actionBar.primaryLabel}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-2.5 py-1.5 text-[11px] font-semibold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Icon
                      name={actionBusy ? 'progress_activity' : primaryActionMeta.icon}
                      className={clsx('text-[15px]', actionBusy && 'animate-spin')}
                    />
                    {actionBusy ? '处理中' : primaryActionMeta.short}
                  </button>
                ) : null}
              </div>
            </div>
          </div>
        </section>

        <section className="flex min-h-0 w-[18.5rem] flex-col gap-3 overflow-y-auto pl-1">
          <div className="rounded-xl bg-surface-container-low p-4 ring-1 ring-outline-variant/8">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-bold text-on-surface">版本历史</h3>
              <span className="text-[11px] text-outline">星标 {starredCount}</span>
            </div>
            <div className="space-y-3">
              {candidateVersions.length === 0 ? (
                <p className="text-xs text-on-surface-variant">暂无版本</p>
              ) : (
                candidateVersions.slice(0, 5).map((version) => (
                  <button
                    key={version.version}
                    type="button"
                    onClick={() => void onSelectVersion('image_generation', version.version)}
                    className={clsx(
                      'flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors',
                      version.version === selectedVersion?.version
                        ? 'bg-primary/10'
                        : 'hover:bg-surface-container',
                    )}
                  >
                    <div className="h-10 w-10 overflow-hidden rounded-lg bg-surface-container-lowest">
                      {version.candidates[0]?.image_url ? (
                        <img
                          src={version.candidates[0].image_url}
                          alt={version.version}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <div className="flex h-full w-full items-center justify-center">
                          <Icon name="image" className="text-xs text-outline" />
                        </div>
                      )}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <p
                          className={clsx(
                            'truncate text-xs font-bold',
                            version.version === selectedVersion?.version ? 'text-on-surface' : 'text-on-surface-variant',
                          )}
                        >
                          {version.version} {version.is_current ? '· 当前采用' : ''}
                        </p>
                        {version.is_starred ? <Icon name="star" className="text-[12px] text-amber-200" /> : null}
                      </div>
                      <p className="text-[11px] text-on-surface-variant">
                        {formatRelativeDate(version.created_at)}
                      </p>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}
