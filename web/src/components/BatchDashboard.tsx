import clsx from 'clsx'
import { useState } from 'react'
import type { GridSheetSummary, ItemSummary, TaskSummary } from '../types'
import { buildImportTemplate, parseImportedItems } from '../lib/itemImport'
import { statusLabel } from '../lib/display'
import { Icon } from './Sidebar'

function stageTone(status: string) {
  if (status === 'completed') return 'text-primary'
  if (
    status === 'image_generated' ||
    status === 'prompt_generated' ||
    status === 'brief_generated'
  ) {
    return 'text-secondary'
  }
  if (status === 'brief_generating' || status === 'prompt_generating') return 'text-sky-300'
  if (status === 'failed') return 'text-error'
  return 'text-on-surface-variant'
}

function statusBadge(status: string) {
  if (status === 'completed') {
    return 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
  }
  if (status === 'failed') {
    return 'border-error/20 bg-error/10 text-error'
  }
  if (status === 'image_generated') {
    return 'border-amber-400/20 bg-amber-400/10 text-amber-300'
  }
  if (status === 'image_generating') {
    return 'border-sky-400/20 bg-sky-400/10 text-sky-300'
  }
  if (status === 'brief_generating' || status === 'prompt_generating') {
    return 'border-sky-400/20 bg-sky-400/10 text-sky-300'
  }
  if (status === 'prompt_generated' || status === 'brief_generated') {
    return 'border-secondary/20 bg-secondary/10 text-secondary-fixed'
  }
  return 'border-outline-variant/20 bg-surface-container-highest text-on-surface-variant'
}

function descriptionFallback(task: TaskSummary) {
  if (task.project_background) return task.project_background
  if (task.style_requirements) return `风格要求：${task.style_requirements}`
  return '这个批次还没有填写项目背景和统一风格要求。'
}

function formatDuration(seconds: number | null | undefined) {
  if (!seconds || seconds <= 0) return '刚开始'
  const totalMinutes = Math.round(seconds / 60)
  if (totalMinutes < 60) return `${totalMinutes}m`
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`
}

function formatPercent(numerator: number, denominator: number) {
  if (denominator <= 0) return '0%'
  return `${Math.round((numerator / denominator) * 100)}%`
}

function reviewLabel(status: string | null | undefined) {
  if (status === 'selected') return '已采纳'
  if (status === 'rejected') return '已废弃'
  if (status === 'emergent') return '涌现好图'
  return '待审'
}

function reviewTone(status: string | null | undefined) {
  if (status === 'selected') return 'border-emerald-300/45 bg-emerald-300/18 text-emerald-100'
  if (status === 'rejected') return 'border-error/45 bg-error/14 text-error'
  if (status === 'emergent') return 'border-amber-300/45 bg-amber-300/18 text-amber-100'
  return 'border-sky-300/28 bg-sky-300/10 text-sky-100'
}

function sheetAspectRatio(value: string | undefined) {
  if (!value || value === 'auto') return '1 / 1'
  return value.replace(':', ' / ')
}

const IMAGE_ASPECT_RATIO_OPTIONS = ['1:1', '3:4', '4:3', '2:3', '3:2', '9:16', '16:9', '21:9']
const IMAGE_RESOLUTION_OPTIONS = ['auto', '512', '1K', '2K', '4K']
const ASSET_TYPE_OPTIONS = [
  { value: 'skill_icon', label: '技能图标', description: '最常见。用于技能、法术、被动、效果图标。' },
  { value: 'item_icon', label: '道具图标', description: '装备、材料、消耗品、宝物。' },
  { value: 'buff_icon', label: '状态图标', description: 'Buff、Debuff、状态效果。' },
  { value: 'generic_icon', label: '通用图标', description: '先不细分时用它，后面也能再调整。' },
  { value: '__custom__', label: '自定义类型', description: '如果你的项目有自己的类型命名，可以手动填。' },
] as const

const CATEGORY_OPTIONS = [
  { value: 'combat', label: '战斗', description: '伤害、技能、武器、攻击类内容。' },
  { value: 'support', label: '辅助', description: '治疗、增益、减益、控制。' },
  { value: 'system', label: '系统', description: '菜单、功能、流程、系统图标。' },
  { value: 'resource', label: '资源', description: '货币、材料、掉落、道具。' },
  { value: '__custom__', label: '自定义标签', description: '如果你有自己的分类体系，可以手动填。' },
] as const

export default function BatchDashboard({
  task,
  items,
  sheets,
  activeItemId,
  onSelectItem,
  onSaveTaskSettings,
  onRunBatchPipeline,
  onExportStarredImages,
  onGridSheetAction,
  onGridSheetTileAction,
  onCreateItem,
  onCreateItemsBulk,
  actionBusy,
  actionError,
}: {
  task: TaskSummary
  items: ItemSummary[]
  sheets: GridSheetSummary[]
  activeItemId: string | null
  onSelectItem: (itemId: string) => void
  onSaveTaskSettings: (payload: {
    task_name: string
    project_background: string
    style_requirements: string
    asset_domain: string
    image_aspect_ratio: string
    image_resolution: string
    image_generation_mode: 'single' | 'grid_sheet'
    grid_rows: number
    grid_cols: number
    grid_padding: number
    grid_gap: number
  }) => Promise<void>
  onRunBatchPipeline: (options?: { autoApprove?: boolean }) => Promise<void>
  onExportStarredImages: () => Promise<void>
  onGridSheetAction: (
    action: 'plan' | 'generate' | 'poll' | 'split' | 'backfill',
    sheetId?: string,
  ) => Promise<void>
  onGridSheetTileAction: (
    action: 'pending' | 'rejected' | 'emergent' | 'promote' | 'create_item',
    sheetId: string,
    cellId: string,
    options?: {
      targetItemId?: string | null
      title?: string
      description?: string
    },
  ) => Promise<void>
  onCreateItem: (payload: {
    asset_type: string
    title: string
    description: string
    category: string
    extra_context: string
  }) => Promise<void>
  onCreateItemsBulk: (payloads: Array<{
    asset_type: string
    title: string
    description: string
    category: string
    extra_context: string
    image_aspect_ratio?: string | null
    image_resolution?: string | null
  }>) => Promise<void>
  actionBusy: boolean
  actionError: string | null
}) {
  const [modal, setModal] = useState<'single' | 'bulk' | null>(null)
  const [settingsExpanded, setSettingsExpanded] = useState(false)
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [category, setCategory] = useState('combat')
  const [customCategory, setCustomCategory] = useState('')
  const [assetType, setAssetType] = useState('skill_icon')
  const [customAssetType, setCustomAssetType] = useState('')
  const [extraContext, setExtraContext] = useState('')
  const [taskName, setTaskName] = useState(task.task_name)
  const [projectBackground, setProjectBackground] = useState(task.project_background)
  const [styleRequirements, setStyleRequirements] = useState(task.style_requirements)
  const [assetDomain, setAssetDomain] = useState(task.asset_domain)
  const [imageAspectRatio, setImageAspectRatio] = useState(
    task.runtime_config?.image_aspect_ratio || '1:1',
  )
  const [imageResolution, setImageResolution] = useState(
    task.runtime_config?.image_resolution || '1K',
  )
  const [imageGenerationMode, setImageGenerationMode] = useState<'single' | 'grid_sheet'>(
    task.runtime_config?.image_generation_mode || 'single',
  )
  const [gridRows, setGridRows] = useState(task.runtime_config?.grid_rows ?? 8)
  const [gridCols, setGridCols] = useState(task.runtime_config?.grid_cols ?? 8)
  const [gridPadding, setGridPadding] = useState(task.runtime_config?.grid_padding ?? 0)
  const [gridGap, setGridGap] = useState(task.runtime_config?.grid_gap ?? 0)
  const [bulkText, setBulkText] = useState('')
  const [bulkSummary, setBulkSummary] = useState<string | null>(null)
  const [sheetSelection, setSheetSelection] = useState<{
    taskId: string
    sheetId: string | null
  }>({ taskId: task.task_id, sheetId: sheets[0]?.sheet_id ?? null })
  const [selectedTileCellId, setSelectedTileCellId] = useState<string | null>(null)
  const [tileTargets, setTileTargets] = useState<Record<string, string>>({})

  const completed = task.items_summary?.completed ?? 0
  const inProgress = task.items_summary?.in_progress ?? 0
  const draft = task.items_summary?.draft ?? 0
  const totalPendingJobs = items.reduce((sum, item) => sum + (item.pending_image_jobs ?? 0), 0)
  const metrics = task.batch_metrics
  const topModelSummary =
    metrics?.top_image_models.map((row) => `${row.model} ×${row.count}`).join(' · ') || '还没有候选图模型数据'
  const selectedSheetId =
    sheetSelection.taskId === task.task_id &&
    sheetSelection.sheetId &&
    sheets.some((sheet) => sheet.sheet_id === sheetSelection.sheetId)
      ? sheetSelection.sheetId
      : sheets[0]?.sheet_id
  const selectedSheet = sheets.find((sheet) => sheet.sheet_id === selectedSheetId) ?? sheets[0]
  const selectedTile =
    (selectedTileCellId && selectedSheet?.tiles.find((tile) => tile.cell_id === selectedTileCellId)) ||
    selectedSheet?.tiles[0] ||
    null
  const selectedTileTarget =
    selectedTile ? (tileTargets[selectedTile.cell_id] ?? selectedTile.target_item_id ?? selectedTile.item_id ?? '') : ''
  const gridSheetEnabled = task.runtime_config?.image_generation_mode === 'grid_sheet'
  const selectedSheetCells = selectedSheet ? `${selectedSheet.input.rows}×${selectedSheet.input.cols}` : `${gridRows}×${gridCols}`
  const selectedSheetPrompt = selectedSheet?.prompt?.prompt ?? ''
  const selectedSheetGenerating = selectedSheet?.status === 'generating'
  const canGenerateSheet = Boolean(selectedSheet && ['planned', 'failed'].includes(selectedSheet.status))
  const canPollSheet = Boolean(selectedSheet && ['generating'].includes(selectedSheet.status))
  const canSplitSheet = Boolean(selectedSheet && ['generated', 'split'].includes(selectedSheet.status))
  const canBackfillSheet = Boolean(
    selectedSheet &&
      selectedSheet.tiles.some((tile) => tile.review_status === 'selected' && !tile.promoted_version),
  )
  const generatedItems = metrics?.generated_items ?? 0
  const completionRate = formatPercent(generatedItems, task.item_count || 0)
  const starredCoverage = formatPercent(metrics?.items_with_starred ?? 0, task.item_count || 0)
  const adoptedFromStarRate = formatPercent(
    metrics?.adopted_from_starred ?? 0,
    metrics?.items_with_starred ?? 0,
  )
  const redoHeadline =
    metrics?.total_redos && task.item_count > 0
      ? `${(metrics.total_redos / task.item_count).toFixed(1)} 次/条`
      : '很稳'
  const redoDetail = metrics
    ? [
        metrics.redo_counts.brief_generation > 0 ? `设计说明 ${metrics.redo_counts.brief_generation}` : null,
        metrics.redo_counts.image_prompt > 0 ? `出图指令 ${metrics.redo_counts.image_prompt}` : null,
        metrics.redo_counts.image_generation > 0 ? `候选图 ${metrics.redo_counts.image_generation}` : null,
      ]
        .filter(Boolean)
        .join(' · ') || '这一轮几乎没返工'
    : '这一轮几乎没返工'
  const failureDetail = metrics
    ? [
        metrics.failure_counts.image_generation > 0 ? `候选图 ${metrics.failure_counts.image_generation}` : null,
        metrics.failure_counts.image_prompt > 0 ? `出图指令 ${metrics.failure_counts.image_prompt}` : null,
        metrics.failure_counts.brief_generation > 0 ? `设计说明 ${metrics.failure_counts.brief_generation}` : null,
        metrics.failure_counts.stale > 0 ? `超时恢复 ${metrics.failure_counts.stale}` : null,
      ]
        .filter(Boolean)
        .join(' · ') || '这一轮没有失败'
    : '这一轮没有失败'
  const rhythmSummary = metrics
    ? [
        `首轮候选 ${formatDuration(metrics.first_image_started_seconds)}`,
        `已出候选 ${generatedItems}/${task.item_count}`,
        `后台任务 ${metrics.active_background_jobs}`,
      ].join(' · ')
    : '这批次还在积累流程数据'

  function resetTaskSettingsDraft() {
    setTaskName(task.task_name)
    setProjectBackground(task.project_background)
    setStyleRequirements(task.style_requirements)
    setAssetDomain(task.asset_domain)
    setImageAspectRatio(task.runtime_config?.image_aspect_ratio || '1:1')
    setImageResolution(task.runtime_config?.image_resolution || '1K')
    setImageGenerationMode(task.runtime_config?.image_generation_mode || 'single')
    setGridRows(task.runtime_config?.grid_rows ?? 8)
    setGridCols(task.runtime_config?.grid_cols ?? 8)
    setGridPadding(task.runtime_config?.grid_padding ?? 0)
    setGridGap(task.runtime_config?.grid_gap ?? 0)
  }

  async function handleBulkFileChange(file: File | null) {
    if (!file) return
    const text = await file.text()
    setBulkText(text)
    const parsed = parseImportedItems(text)
    setBulkSummary(parsed.length > 0 ? `已识别 ${parsed.length} 条记录` : '没有识别到可导入记录')
  }

  async function submitBulkImport() {
    const parsed = parseImportedItems(bulkText)
    if (parsed.length === 0) {
      setBulkSummary('没有识别到可导入记录，请检查表头或内容格式')
      return
    }
    await onCreateItemsBulk(parsed)
    setBulkText('')
    setBulkSummary(null)
    setModal(null)
  }

  function downloadImportTemplate() {
    const content = buildImportTemplate(',')
    const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'ai-icon-pipeline-items-template.csv'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  function resetSingleDraft() {
    setTitle('')
    setDescription('')
    setCategory('combat')
    setCustomCategory('')
    setAssetType('skill_icon')
    setCustomAssetType('')
    setExtraContext('')
  }

  return (
    <div className="flex-1 bg-surface px-4 py-4 md:px-5">
      <section className="mb-4 rounded-xl border border-outline-variant/12 bg-surface-container-low p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex items-center gap-2">
              <span className="rounded-full bg-secondary-container px-2 py-0.5 text-[11px] font-bold text-on-secondary-container">
                {statusLabel(task.status)}
              </span>
            </div>
            <h2 className="text-2xl font-black tracking-tight text-on-surface">{task.task_name}</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-on-surface-variant">
              {descriptionFallback(task)}
            </p>
          </div>

          <div className="grid grid-cols-4 gap-2 lg:min-w-[420px]">
            <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
              <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">条目总数</div>
              <div className="mt-1 text-2xl font-black text-on-surface">{task.item_count}</div>
            </div>
            <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
              <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">待开始</div>
              <div className="mt-1 text-2xl font-black text-on-surface">{draft}</div>
            </div>
            <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
              <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">进行中</div>
              <div className="mt-1 text-2xl font-black text-secondary">{inProgress}</div>
            </div>
            <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
              <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">已完成</div>
              <div className="mt-1 text-2xl font-black text-primary">{completed}</div>
            </div>
          </div>
        </div>
      </section>

      <section className="mb-4 rounded-xl border border-outline-variant/12 bg-surface-container-low p-4">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div className="text-sm font-bold text-on-surface">流程指标</div>
          <div className="text-[11px] text-on-surface-variant">
            只看最关键的四件事：速度、完成度、返工、稳定性。
          </div>
        </div>

        <div className="grid gap-3 xl:grid-cols-4">
          <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">出首图速度</div>
            <div className="mt-1 text-2xl font-black text-on-surface">
              {formatDuration(metrics?.first_image_started_seconds)}
            </div>
            <div className="mt-1 text-xs text-on-surface-variant">
              整批已运行 {formatDuration(metrics?.total_elapsed_seconds)}
            </div>
          </div>
          <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">完成进度</div>
            <div className="mt-1 text-2xl font-black text-on-surface">
              {completionRate}
            </div>
            <div className="mt-1 text-xs text-on-surface-variant">
              已出候选 {generatedItems} / {task.item_count} · 平均流转时长{' '}
              {formatDuration(metrics?.avg_item_elapsed_seconds)}
            </div>
          </div>
          <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">返工压力</div>
            <div className="mt-1 text-2xl font-black text-secondary">{redoHeadline}</div>
            <div className="mt-1 text-xs text-on-surface-variant">{redoDetail}</div>
          </div>
          <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">星标筛选</div>
            <div className="mt-1 text-2xl font-black text-primary">{starredCoverage}</div>
            <div className="mt-1 text-xs text-on-surface-variant">
              {metrics?.starred_images ?? 0} 张星标 · 最终采用来自星标 {adoptedFromStarRate}
            </div>
          </div>
        </div>

        <div className="mt-3 grid gap-3 xl:grid-cols-[1.2fr_1fr_1fr]">
          <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">批次节奏</div>
            <div className="mt-1 text-sm text-on-surface-variant">{rhythmSummary}</div>
          </div>
          <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">后台与失败</div>
            <div className="mt-1 text-sm text-on-surface-variant">
              后台 {metrics?.active_background_jobs ?? totalPendingJobs} 个任务 · {failureDetail}
            </div>
          </div>
          <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
            <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">主要出图模型</div>
            <div className="mt-1 text-sm text-on-surface-variant">{topModelSummary}</div>
          </div>
        </div>
      </section>

      <section className="mb-4 rounded-xl border border-outline-variant/12 bg-surface-container-low">
        <div className="flex flex-col gap-3 px-4 py-3 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <div className="text-sm font-bold text-on-surface">批次设定</div>
              <div className="text-[11px] text-on-surface-variant">批次级公共约束与候选图参数</div>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-on-surface-variant">
              <span className="rounded-full border border-outline-variant/14 bg-surface-container px-2.5 py-1">
                资产域：{task.asset_domain || '未填写'}
              </span>
              <span className="rounded-full border border-outline-variant/14 bg-surface-container px-2.5 py-1">
                出图模式：{task.runtime_config?.image_generation_mode === 'grid_sheet' ? '网格切图' : '单图'}
              </span>
              <span className="rounded-full border border-outline-variant/14 bg-surface-container px-2.5 py-1">
                宽高比：{task.runtime_config?.image_aspect_ratio || '1:1'}
              </span>
              <span className="rounded-full border border-outline-variant/14 bg-surface-container px-2.5 py-1">
                分辨率：{task.runtime_config?.image_resolution || '1K'}
              </span>
            </div>
            <div className="mt-2 grid gap-2 lg:grid-cols-2">
              <div className="min-w-0 rounded-lg border border-outline-variant/12 bg-surface-container px-3 py-2.5">
                <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                  项目背景
                </div>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-on-surface-variant">
                  {task.project_background || '未填写'}
                </p>
              </div>
              <div className="min-w-0 rounded-lg border border-outline-variant/12 bg-surface-container px-3 py-2.5">
                <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                  统一风格要求
                </div>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-on-surface-variant">
                  {task.style_requirements || '未填写'}
                </p>
              </div>
            </div>
          </div>
          <button
            onClick={() => {
              if (settingsExpanded) {
                setSettingsExpanded(false)
                return
              }
              resetTaskSettingsDraft()
              setSettingsExpanded(true)
            }}
            className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container"
          >
            <Icon name={settingsExpanded ? 'expand_less' : 'tune'} className="text-[16px]" />
            {settingsExpanded ? '收起批次设定' : '编辑批次设定'}
          </button>
        </div>

        {settingsExpanded ? (
          <div className="border-t border-outline-variant/10 px-4 pb-3 pt-3">
            <form
              className="grid gap-3"
              onSubmit={async (event) => {
                event.preventDefault()
                await onSaveTaskSettings({
                  task_name: taskName || '未命名批次',
                  project_background: projectBackground,
                  style_requirements: styleRequirements,
                  asset_domain: assetDomain,
                  image_aspect_ratio: imageAspectRatio,
                  image_resolution: imageResolution,
                  image_generation_mode: imageGenerationMode,
                  grid_rows: gridRows,
                  grid_cols: gridCols,
                  grid_padding: gridPadding,
                  grid_gap: gridGap,
                })
                setSettingsExpanded(false)
              }}
            >
              <div className="grid gap-3 lg:grid-cols-[1fr_0.9fr_0.6fr_0.6fr]">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    批次名称
                  </span>
                  <input
                    value={taskName}
                    onChange={(event) => setTaskName(event.target.value)}
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                    placeholder="批次名称"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    资产域
                  </span>
                  <input
                    value={assetDomain}
                    onChange={(event) => setAssetDomain(event.target.value)}
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                    placeholder="game_icon_assets"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    宽高比
                  </span>
                  <select
                    value={imageAspectRatio}
                    onChange={(event) => setImageAspectRatio(event.target.value)}
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  >
                    {IMAGE_ASPECT_RATIO_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    分辨率
                  </span>
                  <select
                    value={imageResolution}
                    onChange={(event) => setImageResolution(event.target.value)}
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  >
                    {IMAGE_RESOLUTION_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="grid gap-3 lg:grid-cols-[0.8fr_0.5fr_0.5fr_0.5fr_0.5fr]">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    出图模式
                  </span>
                  <select
                    value={imageGenerationMode}
                    onChange={(event) =>
                      setImageGenerationMode(event.target.value as 'single' | 'grid_sheet')
                    }
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  >
                    <option value="single">单图模式</option>
                    <option value="grid_sheet">网格切图模式</option>
                  </select>
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    行数
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={gridRows}
                    onChange={(event) => setGridRows(Number(event.target.value))}
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    列数
                  </span>
                  <input
                    type="number"
                    min={1}
                    max={12}
                    value={gridCols}
                    onChange={(event) => setGridCols(Number(event.target.value))}
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    外边距
                  </span>
                  <input
                    type="number"
                    min={0}
                    max={512}
                    value={gridPadding}
                    onChange={(event) => setGridPadding(Number(event.target.value))}
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    间距
                  </span>
                  <input
                    type="number"
                    min={0}
                    max={512}
                    value={gridGap}
                    onChange={(event) => setGridGap(Number(event.target.value))}
                    className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                  />
                </label>
              </div>

              <div className="grid gap-3 lg:grid-cols-2">
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    项目背景
                  </span>
                  <textarea
                    value={projectBackground}
                    onChange={(event) => setProjectBackground(event.target.value)}
                    className="min-h-28 w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm leading-6 text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                    placeholder="低权重背景信息，用于帮助所有条目保持同一世界观。"
                  />
                </label>
                <label className="block">
                  <span className="mb-1.5 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                    统一风格要求
                  </span>
                  <textarea
                    value={styleRequirements}
                    onChange={(event) => setStyleRequirements(event.target.value)}
                    className="min-h-28 w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm leading-6 text-on-surface outline-none ring-1 ring-transparent focus:ring-primary/35"
                    placeholder="例如：统一材质、光照、边框、禁用项。"
                  />
                </label>
              </div>

              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => {
                    resetTaskSettingsDraft()
                    setSettingsExpanded(false)
                  }}
                  className="rounded-xl px-3 py-2 text-xs font-medium text-on-surface-variant transition-colors hover:bg-surface-container"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={actionBusy}
                  className="rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {actionBusy ? '保存中…' : '保存批次设定'}
                </button>
              </div>
            </form>
          </div>
        ) : null}
      </section>

      {gridSheetEnabled ? (
        <section className="mb-4 overflow-hidden rounded-xl border border-outline-variant/12 bg-surface-container-low">
          <div className="flex flex-col gap-3 border-b border-outline-variant/10 px-4 py-3 xl:flex-row xl:items-center xl:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Icon name="grid_view" className="text-[18px] text-primary" />
                <span className="text-sm font-bold text-on-surface">网格切图</span>
                <span className="rounded-full border border-outline-variant/16 bg-surface-container-highest px-2 py-0.5 text-[11px] text-on-surface-variant">
                  {selectedSheet ? `${selectedSheet.sheet_id} · ${statusLabel(selectedSheet.status)}` : '未规划'}
                </span>
                <span className="rounded-full border border-outline-variant/16 bg-surface-container-highest px-2 py-0.5 text-[11px] text-on-surface-variant">
                  {selectedSheetCells}
                </span>
              </div>
              <div className="mt-1 text-xs text-on-surface-variant">
                {selectedSheet
                  ? `当前查看 ${selectedSheet.sheet_id}，目标 ${selectedSheet.input.item_count ?? 0} · 涌现 ${selectedSheet.input.emergent_item_count ?? 0} · 切片 ${selectedSheet.tiles.length} · 剩余 ${selectedSheet.input.remaining_item_count ?? 0}。新建规划会先补齐意图识别。`
                  : `当前会按 ${gridRows * gridCols} 个槽位规划这一批次。`}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {sheets.length > 0 ? (
                <select
                  value={selectedSheet?.sheet_id ?? ''}
                  onChange={(event) =>
                    setSheetSelection({ taskId: task.task_id, sheetId: event.target.value || null })
                  }
                  className="rounded-xl border border-outline-variant/20 bg-surface-container px-3 py-2 text-xs font-bold text-on-surface outline-none transition-colors hover:bg-surface-container-high"
                  aria-label="选择 Sheet 版本"
                >
                  {sheets.map((sheet) => (
                    <option key={sheet.sheet_id} value={sheet.sheet_id}>
                      {sheet.sheet_id} · {statusLabel(sheet.status)}
                    </option>
                  ))}
                </select>
              ) : null}
              <button
                type="button"
                disabled={actionBusy || items.length === 0}
                title="先为缺失的目标 item 生成 brief，再按当前批次设置创建一个新的 sheet_vXXX 规划，不会删除已有图片。"
                onClick={() => {
                  if (
                    sheets.length > 0 &&
                    !window.confirm('这会新建一个 Sheet 规划版本，不会删除已有图片。继续吗？')
                  ) {
                    return
                  }
                  void onGridSheetAction('plan')
                }}
                className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60"
              >
                生成意图并规划
              </button>
              <button
                type="button"
                disabled={actionBusy || !selectedSheet || !canGenerateSheet}
                onClick={() => selectedSheet && void onGridSheetAction('generate', selectedSheet.sheet_id)}
                className="rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-60"
              >
                提交出图
              </button>
              <button
                type="button"
                disabled={actionBusy || !selectedSheet || !canPollSheet}
                onClick={() => selectedSheet && void onGridSheetAction('poll', selectedSheet.sheet_id)}
                className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60"
              >
                轮询结果
              </button>
              <button
                type="button"
                disabled={actionBusy || !selectedSheet || !canSplitSheet}
                onClick={() => selectedSheet && void onGridSheetAction('split', selectedSheet.sheet_id)}
                className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60"
              >
                切图
              </button>
              <button
                type="button"
                disabled={actionBusy || !selectedSheet || !canBackfillSheet}
                onClick={() => selectedSheet && void onGridSheetAction('backfill', selectedSheet.sheet_id)}
                className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60"
              >
                采纳选中
              </button>
            </div>
          </div>

          {selectedSheet ? (
            <div className="grid gap-0 lg:grid-cols-[minmax(320px,0.9fr)_minmax(0,1.1fr)]">
              <div className="border-b border-outline-variant/10 bg-surface-container px-4 py-4 lg:border-b-0 lg:border-r">
                <div
                  className="relative flex items-center justify-center overflow-hidden rounded-xl border border-outline-variant/14 bg-surface-container-highest"
                  style={{ aspectRatio: sheetAspectRatio(selectedSheet.input.image_aspect_ratio) }}
                >
                  {selectedSheet.source_image_url ? (
                    <>
                      <img
                        src={selectedSheet.source_image_url}
                        alt={selectedSheet.sheet_id}
                        className="h-full w-full object-contain"
                      />
                      <div
                        className="absolute inset-0 grid"
                        style={{
                          gridTemplateColumns: `repeat(${selectedSheet.input.cols}, minmax(0, 1fr))`,
                          gridTemplateRows: `repeat(${selectedSheet.input.rows}, minmax(0, 1fr))`,
                        }}
                      >
                        {selectedSheet.tiles.map((tile) => {
                          const isActive = selectedTile?.cell_id === tile.cell_id
                          return (
                            <button
                              key={tile.cell_id}
                              type="button"
                              title={`${tile.cell_id} · ${reviewLabel(tile.review_status)}`}
                              onClick={() => setSelectedTileCellId(tile.cell_id)}
                              className={clsx(
                                'group relative border border-sky-300/70 bg-sky-300/0 transition-colors hover:bg-sky-300/12',
                                isActive && 'z-10 border-2 border-primary bg-primary/10',
                                tile.review_status === 'selected' && 'bg-emerald-300/12',
                                tile.review_status === 'rejected' && 'bg-error/16',
                                tile.review_status === 'emergent' && 'bg-amber-300/14',
                              )}
                            >
                              <span
                                className={clsx(
                                  'absolute left-1 top-1 rounded-full border px-1.5 py-0.5 text-[10px] font-bold opacity-0 shadow-sm transition-opacity group-hover:opacity-100',
                                  reviewTone(tile.review_status),
                                  isActive && 'opacity-100',
                                )}
                              >
                                {tile.cell_id}
                              </span>
                              {tile.promoted_version ? (
                                <span className="absolute right-1 top-1 rounded-full bg-emerald-300 px-1.5 py-0.5 text-[10px] font-black text-emerald-950">
                                  ★
                                </span>
                              ) : null}
                            </button>
                          )
                        })}
                      </div>
                    </>
                  ) : selectedSheetGenerating ? (
                    <div className="flex h-full w-full flex-col items-center justify-center gap-3 px-6 text-center">
                      <div className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/25 bg-primary/10">
                        <div className="h-7 w-7 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                      </div>
                      <div>
                        <div className="text-sm font-black text-on-surface">Sheet 正在生成中</div>
                        <div className="mt-1 text-xs leading-5 text-on-surface-variant">
                          已提交到 Provider，等待轮询结果。这里不展示假进度，只提示任务还在跑。
                        </div>
                      </div>
                      {selectedSheet.async_job?.task_id ? (
                        <div className="max-w-full truncate rounded-full border border-outline-variant/16 bg-surface-container px-2.5 py-1 font-mono text-[10px] text-outline">
                          {selectedSheet.async_job.task_id}
                        </div>
                      ) : null}
                    </div>
                  ) : (
                    <Icon name="image" className="text-[34px] text-outline" />
                  )}
                </div>
                <div className="mt-2 text-[11px] leading-5 text-on-surface-variant">
                  蓝线是系统真实切分层，采纳时按这套边界切片入池。
                </div>
                <div className="mt-3 grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-lg bg-surface-container-highest px-2 py-2">
                    <div className="text-[11px] text-outline">槽位</div>
                    <div className="text-sm font-black text-on-surface">{selectedSheet.slots.length}</div>
                  </div>
                  <div className="rounded-lg bg-surface-container-highest px-2 py-2">
                    <div className="text-[11px] text-outline">切片</div>
                    <div className="text-sm font-black text-on-surface">{selectedSheet.tiles.length}</div>
                  </div>
                  <div className="rounded-lg bg-surface-container-highest px-2 py-2">
                    <div className="text-[11px] text-outline">任务</div>
                    <div className="text-sm font-black text-on-surface">
                      {selectedSheetGenerating ? '运行中' : `${selectedSheet.async_job?.progress ?? 0}%`}
                    </div>
                  </div>
                </div>
              </div>
              <div className="min-w-0 px-4 py-4">
                {selectedTile ? (
                  <div className="mb-3 grid gap-3 xl:grid-cols-[220px_minmax(0,1fr)]">
                    <div className="overflow-hidden rounded-lg border border-outline-variant/12 bg-surface-container">
                      {selectedTile.image_url ? (
                        <img src={selectedTile.image_url} alt={selectedTile.cell_id} className="aspect-square w-full object-cover" />
                      ) : (
                        <div className="flex aspect-square items-center justify-center">
                          <Icon name="image" className="text-[28px] text-outline" />
                        </div>
                      )}
                    </div>
                    <div className="rounded-lg border border-outline-variant/12 bg-surface-container px-3 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-sm font-black text-on-surface">{selectedTile.cell_id}</span>
                        <span className={clsx('rounded-full border px-2 py-0.5 text-[11px] font-bold', reviewTone(selectedTile.review_status))}>
                          {reviewLabel(selectedTile.review_status)}
                        </span>
                        {selectedTile.promoted_version ? (
                          <span className="rounded-full border border-emerald-300/35 bg-emerald-300/12 px-2 py-0.5 text-[11px] font-bold text-emerald-100">
                            已入池并星标
                          </span>
                        ) : null}
                      </div>
                      <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
                        <select
                          value={selectedTileTarget}
                          onChange={(event) =>
                            setTileTargets((current) => ({ ...current, [selectedTile.cell_id]: event.target.value }))
                          }
                          className="min-w-0 rounded-xl border border-outline-variant/20 bg-surface-container-highest px-3 py-2 text-xs font-bold text-on-surface outline-none"
                        >
                          <option value="">未绑定 item</option>
                          {items.map((item) => (
                            <option key={item.item_id} value={item.item_id}>
                              {item.item_id} · {item.title || '未命名'}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          disabled={actionBusy || Boolean(selectedTile.promoted_version) || !selectedTileTarget}
                          onClick={() =>
                            void onGridSheetTileAction('promote', selectedSheet.sheet_id, selectedTile.cell_id, {
                              targetItemId: selectedTileTarget,
                            })
                          }
                          className="rounded-xl bg-primary px-3 py-2 text-xs font-black text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          采纳并星标
                        </button>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          disabled={actionBusy}
                          onClick={() => void onGridSheetTileAction('rejected', selectedSheet.sheet_id, selectedTile.cell_id)}
                          className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container-high disabled:opacity-60"
                        >
                          废弃
                        </button>
                        <button
                          type="button"
                          disabled={actionBusy}
                          onClick={() => void onGridSheetTileAction('emergent', selectedSheet.sheet_id, selectedTile.cell_id)}
                          className="rounded-xl border border-amber-300/30 px-3 py-2 text-xs font-bold text-amber-100 transition-colors hover:bg-amber-300/10 disabled:opacity-60"
                        >
                          标记涌现好图
                        </button>
                        <button
                          type="button"
                          disabled={actionBusy || Boolean(selectedTile.promoted_version)}
                          onClick={() => {
                            const suggested = `涌现图标 ${selectedTile.cell_id}`
                            const createdTitle = window.prompt('给这个涌现切片命名', suggested)
                            if (!createdTitle) return
                            void onGridSheetTileAction('create_item', selectedSheet.sheet_id, selectedTile.cell_id, {
                              title: createdTitle,
                              description: `从 ${selectedSheet.sheet_id} ${selectedTile.cell_id} 采纳的涌现技能图标。`,
                            })
                          }}
                          className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container-high disabled:opacity-60"
                        >
                          创建 item 并采纳
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}
                <div className="grid gap-3 xl:grid-cols-2">
                  <div className="min-w-0 rounded-lg border border-outline-variant/12 bg-surface-container px-3 py-3">
                    <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                      Sheet Prompt
                    </div>
                    <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-on-surface-variant">
                      {selectedSheetPrompt || '尚未生成 prompt'}
                    </pre>
                  </div>
                  <div className="min-w-0 rounded-lg border border-outline-variant/12 bg-surface-container px-3 py-3">
                    <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                      最近槽位
                    </div>
                    <div className="mt-2 grid max-h-52 gap-1.5 overflow-auto">
                      {selectedSheet.slots.slice(0, 12).map((slot) => (
                        <div
                          key={slot.cell_id}
                          className="grid grid-cols-[74px_minmax(0,1fr)] gap-2 rounded-lg bg-surface-container-highest px-2 py-1.5 text-[11px]"
                        >
                          <span className="font-mono text-outline">{slot.cell_id}</span>
                          <span className="truncate text-on-surface-variant">{slot.title || slot.item_id}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-outline-variant/12 bg-surface-container-low">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant/10 px-4 py-3">
          <div className="flex items-center gap-2">
            <Icon name="view_list" className="text-[18px] text-primary" />
            <span className="text-sm font-bold text-on-surface">条目概览</span>
            <span className="text-xs text-on-surface-variant">在一个屏幕里快速浏览状态和版本</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setModal('bulk')}
              className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container"
            >
              CSV / 表格导入
            </button>
            <button
              onClick={() => {
                resetSingleDraft()
                setModal('single')
              }}
              className="flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim"
            >
              <Icon name="add" className="text-[16px]" />
              新增条目
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant/10 bg-surface-container-lowest/20 px-4 py-3">
          <div>
            <div className="text-sm font-bold text-on-surface">批次总控制</div>
            <div className="mt-1 text-xs text-on-surface-variant">
              一次推进整个批次。当前先按顺序执行，更稳；后面再加可控并发。
              {totalPendingJobs > 0 ? ` 现在后台还有 ${totalPendingJobs} 个候选图任务在跑。` : ''}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={actionBusy || items.length === 0}
              onClick={() => void onExportStarredImages()}
              className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60"
            >
              {actionBusy ? '处理中…' : '导出星标 ZIP'}
            </button>
            <button
              type="button"
              disabled={actionBusy || items.length === 0}
              onClick={() => void onRunBatchPipeline({ autoApprove: false })}
              className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-60"
            >
              {actionBusy ? '执行中…' : '推进到待审核'}
            </button>
            <button
              type="button"
              disabled={actionBusy || items.length === 0}
              onClick={() => void onRunBatchPipeline({ autoApprove: true })}
              className="rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-60"
            >
              {actionBusy ? '执行中…' : '一键跑完整个批次'}
            </button>
          </div>
        </div>

        {actionError ? (
          <div className="border-b border-error/20 bg-error/10 px-4 py-2 text-sm text-error">
            {actionError}
          </div>
        ) : null}

        <div className="overflow-hidden">
          <table className="w-full table-fixed text-left">
            <colgroup>
              <col className="w-[132px]" />
              <col />
              <col className="w-[172px]" />
              <col className="w-[92px]" />
            </colgroup>
            <thead>
              <tr className="border-b border-outline-variant/10 bg-surface-container-lowest/20 text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
                <th className="px-4 py-2.5">预览</th>
                <th className="px-4 py-2.5">条目</th>
                <th className="px-4 py-2.5">状态</th>
                <th className="px-4 py-2.5">当前版本</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/10">
              {items.map((item) => {
                const isActive = item.item_id === activeItemId
                const currentVersion =
                  item.current_versions?.image_generation ||
                  item.current_versions?.image_prompt ||
                  item.current_versions?.brief_generation ||
                  '无'
                const pendingImageJobs = item.pending_image_jobs ?? 0
                const effectiveStatus = pendingImageJobs > 0 ? 'image_generating' : item.status

                return (
                  <tr
                    key={item.item_id}
                    className={clsx(
                      'group cursor-pointer transition-colors hover:bg-primary/8',
                      isActive && 'bg-surface-container-lowest/20',
                    )}
                    onClick={() => onSelectItem(item.item_id)}
                  >
                    <td className="px-3 py-3 align-top">
                      <div
                        className={clsx(
                          'flex h-[96px] w-[96px] items-center justify-center overflow-hidden rounded-2xl border bg-surface-container-highest shadow-[0_10px_18px_rgba(0,0,0,0.16)] transition-all group-hover:-translate-y-0.5 group-hover:border-primary/35 group-hover:shadow-[0_14px_24px_rgba(0,0,0,0.2)]',
                          isActive ? 'border-primary/30' : 'border-outline-variant/18',
                        )}
                      >
                        {item.preview_image_url ? (
                          <img
                            src={item.preview_image_url}
                            alt={item.title}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <Icon name="image" className="text-[28px] text-outline" />
                        )}
                      </div>
                    </td>

                    <td className="px-3 py-3 align-top">
                      <div className="flex h-[96px] flex-col justify-center overflow-hidden">
                        <div className="flex items-center gap-2">
                          <div
                            className={clsx(
                              'line-clamp-2 text-[0.98rem] font-black leading-5 transition-colors group-hover:text-primary',
                              isActive ? 'text-primary' : 'text-on-surface',
                            )}
                          >
                            {item.title}
                          </div>
                          <span
                            className={clsx(
                              'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition-all',
                              isActive
                                ? 'border-primary/30 bg-primary/12 text-primary'
                                : 'border-outline-variant/15 bg-surface-container-highest text-outline group-hover:border-primary/30 group-hover:bg-primary/10 group-hover:text-primary',
                            )}
                            title="进入工作台"
                          >
                            <Icon name="arrow_forward" className="text-[16px]" />
                          </span>
                        </div>
                        <div className="mt-2 line-clamp-2 text-[0.82rem] leading-5 text-on-surface-variant">
                          {item.description || item.item_id}
                        </div>
                      </div>
                    </td>

                    <td className="px-3 py-3 align-top">
                      <div className="flex h-[96px] items-center">
                        <span
                          className={clsx(
                            'inline-flex max-w-full items-center gap-2 rounded-full border px-2.5 py-1.5 text-[0.82rem] font-bold',
                            statusBadge(effectiveStatus),
                            stageTone(effectiveStatus),
                          )}
                        >
                          <span className="h-2 w-2 rounded-full bg-current" />
                          <span className="truncate">
                            {pendingImageJobs > 0 ? `生成中 · ${pendingImageJobs}` : statusLabel(item.status)}
                          </span>
                        </span>
                      </div>
                    </td>

                    <td className="px-3 py-3 align-top">
                      <div className="flex h-[96px] items-center">
                        <span className="rounded-lg border border-outline-variant/18 bg-surface-container-highest px-2 py-1 font-mono text-[0.78rem] text-on-surface-variant">
                          {currentVersion}
                        </span>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {items.length === 0 ? (
          <div className="flex min-h-[180px] flex-col items-center justify-center p-8 text-center">
            <Icon name="inbox" className="mb-3 text-3xl text-outline" />
            <p className="text-sm text-on-surface-variant">当前批次还没有条目</p>
            <p className="mt-2 text-xs text-outline">可以先新增条目，也可以一次性导入 CSV 或表格数据。</p>
          </div>
        ) : null}
      </section>

      {modal === 'single' ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-6 backdrop-blur-sm">
          <button
            type="button"
            className="absolute inset-0"
            aria-label="关闭新增条目"
            onClick={() => {
              setModal(null)
              resetSingleDraft()
            }}
          />
          <form
            className="relative z-10 w-full max-w-3xl overflow-hidden rounded-[28px] border border-outline-variant/12 bg-surface-container-low shadow-[0_28px_80px_rgba(0,0,0,0.45)]"
            onSubmit={async (event) => {
              event.preventDefault()
              await onCreateItem({
                asset_type: assetType === '__custom__' ? customAssetType.trim() || 'generic_icon' : assetType,
                title,
                description,
                category: category === '__custom__' ? customCategory.trim() || 'custom' : category,
                extra_context: extraContext,
              })
              resetSingleDraft()
              setModal(null)
            }}
          >
            <div className="border-b border-outline-variant/10 bg-[radial-gradient(circle_at_top_left,_rgba(161,155,255,0.16),_transparent_38%),linear-gradient(180deg,_rgba(17,26,49,0.96)_0%,_rgba(12,20,38,0.96)_100%)] px-6 py-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-outline">
                    Create Item
                  </div>
                  <h3 className="mt-2 text-[1.7rem] font-black tracking-tight text-on-surface">
                    新增条目
                  </h3>
                  <p className="mt-2 max-w-xl text-sm leading-6 text-on-surface-variant">
                    一个条目就是一个具体要做的 icon。先把名称和需求说清楚，再决定它属于什么类型。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setModal(null)
                    resetSingleDraft()
                  }}
                  className="rounded-xl border border-outline-variant/14 bg-surface-container/60 p-2 text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
                >
                  <Icon name="close" className="text-[18px]" />
                </button>
              </div>
            </div>

            <div className="grid gap-0 lg:grid-cols-[0.92fr_1.08fr]">
              <div className="border-b border-outline-variant/10 bg-surface-container px-6 py-6 lg:border-b-0 lg:border-r">
                <div className="rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-4">
                  <div className="mb-3 flex items-center gap-2 text-primary">
                    <Icon name="inventory_2" filled className="text-[18px]" />
                    <span className="text-sm font-bold text-on-surface">怎么理解这几个字段</span>
                  </div>
                  <div className="space-y-3 text-sm text-on-surface-variant">
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">条目名称</div>
                      <div className="mt-1 leading-6">这个 icon 的名字，例如“雷暴”“治疗术”“火球”。</div>
                    </div>
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">条目类型</div>
                      <div className="mt-1 leading-6">更偏技术上的归类，主要帮助后面统一管理和扩展。</div>
                    </div>
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">标签分类</div>
                      <div className="mt-1 leading-6">更偏业务上的分组，比如战斗、辅助、资源。后面筛选会用到。</div>
                    </div>
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">条目描述</div>
                      <div className="mt-1 leading-6">直接写用户需求，越具体越好。</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-6">
                <div className="space-y-4">
                  <label className="block">
                    <span className="mb-2 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                      条目名称
                    </span>
                    <input
                      value={title}
                      onChange={(event) => setTitle(event.target.value)}
                      className="w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-[1.05rem] font-semibold text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                      placeholder="例如：赵云、雷暴、烈焰回旋斧"
                      autoFocus
                    />
                  </label>

                  <div className="grid gap-4 lg:grid-cols-2">
                    <label className="block">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                          条目类型
                        </span>
                        <span className="text-[11px] text-outline">偏技术归类</span>
                      </div>
                      <select
                        value={assetType}
                        onChange={(event) => setAssetType(event.target.value)}
                        className="w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm text-on-surface outline-none transition-colors focus:border-primary/35"
                      >
                        {ASSET_TYPE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <p className="mt-2 text-xs leading-5 text-on-surface-variant">
                        {ASSET_TYPE_OPTIONS.find((option) => option.value === assetType)?.description}
                      </p>
                      {assetType === '__custom__' ? (
                        <input
                          value={customAssetType}
                          onChange={(event) => setCustomAssetType(event.target.value)}
                          className="mt-2 w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                          placeholder="输入你自己的条目类型，例如 hero_icon"
                        />
                      ) : null}
                    </label>

                    <label className="block">
                      <div className="mb-2 flex items-center justify-between gap-3">
                        <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                          标签分类
                        </span>
                        <span className="text-[11px] text-outline">偏业务分组</span>
                      </div>
                      <select
                        value={category}
                        onChange={(event) => setCategory(event.target.value)}
                        className="w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm text-on-surface outline-none transition-colors focus:border-primary/35"
                      >
                        {CATEGORY_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                      <p className="mt-2 text-xs leading-5 text-on-surface-variant">
                        {CATEGORY_OPTIONS.find((option) => option.value === category)?.description}
                      </p>
                      {category === '__custom__' ? (
                        <input
                          value={customCategory}
                          onChange={(event) => setCustomCategory(event.target.value)}
                          className="mt-2 w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                          placeholder="输入你自己的标签，例如 warrior / mage / ui"
                        />
                      ) : null}
                    </label>
                  </div>

                  <label className="block">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                        条目描述
                      </span>
                      <span className="text-[11px] text-outline">真正的用户需求</span>
                    </div>
                    <textarea
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                      className="min-h-28 w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm leading-6 text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                      placeholder="直接写这个 icon 要表达什么、长什么样、重点突出什么。"
                    />
                  </label>

                  <label className="block">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                        补充说明
                      </span>
                      <span className="text-[11px] text-outline">可选</span>
                    </div>
                    <textarea
                      value={extraContext}
                      onChange={(event) => setExtraContext(event.target.value)}
                      className="min-h-20 w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm leading-6 text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                      placeholder="比如颜色偏好、参考元素、禁用元素、和同批次其他 icon 的关系。"
                    />
                  </label>
                </div>

                <div className="mt-6 flex items-center justify-between gap-3">
                  <div className="text-xs text-on-surface-variant">
                    创建后可以继续编辑，也可以批量再导入更多条目。
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setModal(null)
                        resetSingleDraft()
                      }}
                      className="rounded-xl px-4 py-2.5 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      disabled={actionBusy}
                      className="rounded-2xl bg-primary px-5 py-2.5 text-sm font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {actionBusy ? '创建中…' : '创建条目'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </form>
        </div>
      ) : null}

      {modal === 'bulk' ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-6 backdrop-blur-sm">
          <div className="w-full max-w-3xl rounded-xl bg-surface-container-low p-5 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-on-surface">批量导入条目</h3>
                <p className="mt-1 text-sm text-on-surface-variant">
                  支持 CSV、TSV 或直接粘贴表格。常见表头：名称、需求描述、资产类型、分类、额外上下文。
                </p>
              </div>
              <button
                type="button"
                onClick={() => setModal(null)}
                className="rounded p-1 text-on-surface-variant hover:bg-surface-container"
              >
                <Icon name="close" className="text-base" />
              </button>
            </div>

            <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
              <div className="rounded-xl border border-outline-variant/15 bg-surface-container p-4">
                <div className="text-sm font-bold text-on-surface">导入方式</div>
                <label className="mt-3 flex cursor-pointer items-center justify-center rounded-xl border border-dashed border-outline-variant/20 bg-surface-container-lowest/40 px-3 py-6 text-center text-sm text-on-surface-variant hover:border-primary/25 hover:text-on-surface">
                  <input
                    type="file"
                    accept=".csv,.tsv,text/csv,text/tab-separated-values"
                    className="hidden"
                    onChange={(event) => {
                      void handleBulkFileChange(event.target.files?.[0] ?? null)
                    }}
                  />
                  选择 CSV / TSV 文件
                </label>
                <button
                  type="button"
                  onClick={downloadImportTemplate}
                  className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-outline-variant/20 px-3 py-3 text-sm font-bold text-on-surface transition-colors hover:bg-surface-container-high"
                >
                  <Icon name="download" className="text-[16px]" />
                  下载 CSV 模板
                </button>
                <div className="mt-3 text-xs leading-5 text-on-surface-variant">
                  CSV 是逗号分隔；TSV 是 Tab 分隔，更适合直接从 Excel / 飞书表格复制粘贴。
                </div>
                <div className="mt-2 text-xs leading-5 text-outline">
                  推荐先下载模板填充，再导入；也可以直接把 Excel / 飞书表格内容复制后粘贴到右侧文本框。
                </div>
              </div>

              <div>
                <textarea
                  value={bulkText}
                  onChange={(event) => {
                    setBulkText(event.target.value)
                    const parsed = parseImportedItems(event.target.value)
                    setBulkSummary(parsed.length > 0 ? `已识别 ${parsed.length} 条记录` : null)
                  }}
                  className="min-h-[300px] w-full rounded-xl border border-outline-variant/15 bg-surface-container-lowest/50 p-4 font-mono text-[12px] leading-6 text-on-surface outline-none focus:border-primary/35"
                  placeholder={'名称,需求描述,资产类型,分类,额外上下文\n雷暴,对敌人造成雷电伤害,skill_icon,combat,蓝白主色'}
                />
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-on-surface-variant">{bulkSummary ?? '准备好后点击导入'}</span>
                  <span className="text-outline">支持无表头粘贴，按列顺序自动识别</span>
                </div>
              </div>
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setModal(null)}
                className="rounded px-3 py-2 text-xs text-on-surface-variant hover:bg-surface-container"
              >
                取消
              </button>
              <button
                type="button"
                disabled={actionBusy}
                onClick={() => void submitBulkImport()}
                className="rounded-xl bg-primary px-4 py-2 text-xs font-bold text-on-primary-fixed disabled:opacity-50"
              >
                {actionBusy ? '导入中…' : '导入条目'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
