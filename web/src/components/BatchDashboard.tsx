import clsx from 'clsx'
import { useState, type PointerEvent } from 'react'
import type { GridSheetSummary, ItemSummary, TaskSummary } from '../types'
import { buildImportTemplate, parseImportedItems } from '../lib/itemImport'
import { statusLabel } from '../lib/display'
import { Icon } from './Sidebar'

type CropBoxPercent = {
  left: number
  top: number
  right: number
  bottom: number
}

type GridLinesPercent = {
  x: number[]
  y: number[]
}

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

function clampCropBox(box: CropBoxPercent): CropBoxPercent {
  const left = Math.min(Math.max(box.left, 0), 95)
  const top = Math.min(Math.max(box.top, 0), 95)
  const right = Math.min(Math.max(box.right, left + 5), 100)
  const bottom = Math.min(Math.max(box.bottom, top + 5), 100)
  return { left, top, right, bottom }
}

function cropBoxFromSheet(sheet: GridSheetSummary | undefined): CropBoxPercent {
  const saved = sheet?.split_config?.crop_box_percent
  if (saved) {
    return clampCropBox({
      left: Number(saved.left),
      top: Number(saved.top),
      right: Number(saved.right),
      bottom: Number(saved.bottom),
    })
  }
  return { left: 0, top: 0, right: 100, bottom: 100 }
}

function cropBoxStyle(box: CropBoxPercent) {
  return {
    left: `${box.left}%`,
    top: `${box.top}%`,
    width: `${box.right - box.left}%`,
    height: `${box.bottom - box.top}%`,
  }
}

function equalLines(count: number, start = 0, end = 100) {
  return Array.from({ length: count + 1 }, (_, index) => start + ((end - start) * index) / count)
}

function clampLine(lines: number[], index: number, value: number) {
  const next = [...lines]
  const minGap = 0.2
  const min = index === 0 ? 0 : next[index - 1] + minGap
  const max = index === next.length - 1 ? 100 : next[index + 1] - minGap
  next[index] = Math.min(Math.max(value, min), max)
  return next
}

function linesFromSheet(sheet: GridSheetSummary | undefined): GridLinesPercent {
  const crop = cropBoxFromSheet(sheet)
  const cols = sheet?.input.cols ?? 1
  const rows = sheet?.input.rows ?? 1
  const savedX = sheet?.split_config?.x_lines_percent
  const savedY = sheet?.split_config?.y_lines_percent
  return {
    x: savedX && savedX.length === cols + 1 ? savedX.map(Number) : equalLines(cols, crop.left, crop.right),
    y: savedY && savedY.length === rows + 1 ? savedY.map(Number) : equalLines(rows, crop.top, crop.bottom),
  }
}

function cropBoxFromLines(lines: GridLinesPercent): CropBoxPercent {
  return clampCropBox({
    left: lines.x[0] ?? 0,
    top: lines.y[0] ?? 0,
    right: lines.x[lines.x.length - 1] ?? 100,
    bottom: lines.y[lines.y.length - 1] ?? 100,
  })
}

function cellBoxStyle(lines: GridLinesPercent, row: number, col: number) {
  const left = lines.x[col - 1] ?? 0
  const right = lines.x[col] ?? left
  const top = lines.y[row - 1] ?? 0
  const bottom = lines.y[row] ?? top
  return {
    left: `${left}%`,
    top: `${top}%`,
    width: `${Math.max(0, right - left)}%`,
    height: `${Math.max(0, bottom - top)}%`,
  }
}

const IMAGE_ASPECT_RATIO_OPTIONS = ['1:1', '3:4', '4:3', '2:3', '3:2', '9:16', '16:9', '21:9']
const IMAGE_RESOLUTION_OPTIONS = ['auto', '512', '1K', '2K', '4K']
const ASSET_TYPE_OPTIONS = [
  { value: 'skill_icon', label: '技能图标', description: '最常见。用于技能、法术、被动、效果图标。' },
  { value: 'item_icon', label: '道具图标', description: '装备、材料、消耗品、宝物。' },
  { value: 'buff_icon', label: '状态图标', description: '增益、减益、状态效果。' },
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
    options?: {
      cropBoxPercent?: CropBoxPercent
      xLinesPercent?: number[]
      yLinesPercent?: number[]
    },
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
  const [lineDrafts, setLineDrafts] = useState<Record<string, GridLinesPercent>>({})
  const [dragLine, setDragLine] = useState<{
    sheetId: string
    axis: 'x' | 'y'
    index: number
  } | null>(null)

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
  const selectedSheetLines = selectedSheet
    ? (lineDrafts[selectedSheet.sheet_id] ?? linesFromSheet(selectedSheet))
    : { x: [0, 100], y: [0, 100] }
  const selectedSheetCrop = cropBoxFromLines(selectedSheetLines)
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
  const canSplitSheet = Boolean(
    selectedSheet?.source_image_url && !['planned', 'generating'].includes(selectedSheet.status),
  )
  const canBackfillSheet = Boolean(
    selectedSheet &&
      selectedSheet.tiles.some((tile) => tile.review_status === 'selected' && !tile.promoted_version),
  )
  const sheetReviewCounts = selectedSheet
    ? selectedSheet.tiles.reduce(
        (counts, tile) => {
          const status = tile.review_status || 'pending'
          if (status === 'selected') counts.selected += 1
          else if (status === 'rejected') counts.rejected += 1
          else if (status === 'emergent') counts.emergent += 1
          else counts.pending += 1
          if (tile.promoted_version) counts.promoted += 1
          return counts
        },
        { pending: 0, selected: 0, rejected: 0, emergent: 0, promoted: 0 },
      )
    : { pending: 0, selected: 0, rejected: 0, emergent: 0, promoted: 0 }
  const selectedSheetBoundSlots = selectedSheet?.slots.filter((slot) => slot.kind !== 'emergent').length ?? 0
  const selectedSheetEmergentSlots = selectedSheet?.slots.filter((slot) => slot.kind === 'emergent').length ?? 0
  const selectedSheetBriefsReady =
    selectedSheet?.brief_generation?.generated || selectedSheet?.brief_generation?.existing
      ? (selectedSheet.brief_generation.generated ?? 0) + (selectedSheet.brief_generation.existing ?? 0)
      : selectedSheetBoundSlots
  const selectedTileSlot = selectedSheet?.slots.find((slot) => slot.cell_id === selectedTile?.cell_id)
  const selectedTileLinkedItem = items.find((item) => item.item_id === selectedTileTarget)
  function updateSelectedSheetLine(axis: 'x' | 'y', index: number, value: number) {
    if (!selectedSheet) return
    setLineDrafts((current) => {
      const currentLines = current[selectedSheet.sheet_id] ?? linesFromSheet(selectedSheet)
      return {
        ...current,
        [selectedSheet.sheet_id]: {
          x: axis === 'x' ? clampLine(currentLines.x, index, value) : currentLines.x,
          y: axis === 'y' ? clampLine(currentLines.y, index, value) : currentLines.y,
        },
      }
    })
  }

  function resetSelectedSheetLines() {
    if (!selectedSheet) return
    setLineDrafts((current) => ({
      ...current,
      [selectedSheet.sheet_id]: {
        x: equalLines(selectedSheet.input.cols, 0, 100),
        y: equalLines(selectedSheet.input.rows, 0, 100),
      },
    }))
  }

  function handleCutLinePointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!selectedSheet || !dragLine || dragLine.sheetId !== selectedSheet.sheet_id) return
    const rect = event.currentTarget.getBoundingClientRect()
    const value =
      dragLine.axis === 'x'
        ? ((event.clientX - rect.left) / rect.width) * 100
        : ((event.clientY - rect.top) / rect.height) * 100
    updateSelectedSheetLine(dragLine.axis, dragLine.index, value)
  }

  function handleCutLinePointerDown(
    event: PointerEvent<HTMLButtonElement>,
    axis: 'x' | 'y',
    index: number,
  ) {
    if (!selectedSheet) return
    event.preventDefault()
    event.stopPropagation()
    event.currentTarget.setPointerCapture(event.pointerId)
    setDragLine({ sheetId: selectedSheet.sheet_id, axis, index })
  }

  function handleCreateSheetRun() {
    if (sheets.length > 0 && !window.confirm('这会新建一张整图规划，不会删除已有图片。继续吗？')) {
      return
    }
    setSheetSelection({ taskId: task.task_id, sheetId: null })
    void onGridSheetAction('plan')
  }
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
              <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">目标总数</div>
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
                    placeholder="低权重背景信息，用于帮助所有目标保持同一世界观。"
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
          <div className="border-b border-outline-variant/10 px-4 py-3">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Icon name="grid_view" className="text-[18px] text-primary" />
                  <span className="text-sm font-black text-on-surface">网格整图工作流</span>
                  <span className="rounded-full border border-outline-variant/16 bg-surface-container-highest px-2 py-0.5 text-[11px] text-on-surface-variant">
                    {selectedSheet ? `${selectedSheet.sheet_id} · ${statusLabel(selectedSheet.status)}` : '等待规划'}
                  </span>
                  <span className="rounded-full border border-outline-variant/16 bg-surface-container-highest px-2 py-0.5 text-[11px] text-on-surface-variant">
                    {selectedSheetCells}
                  </span>
                </div>
                <div className="mt-1 text-xs leading-5 text-on-surface-variant">
                  目标资产先做意图识别；每张整图负责一次批量生成；切片审图决定哪些小图进入候选池。
                </div>
              </div>
              <button
                type="button"
                disabled={actionBusy || items.length === 0}
                title="按当前目标和批次设置，新建一张整图规划。不会删除旧图。"
                onClick={handleCreateSheetRun}
                className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-primary px-3 py-2 text-xs font-black text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Icon name="add" className="text-[16px]" />
                新建整图规划
              </button>
            </div>
          </div>

          <div className="grid gap-4 p-4 xl:grid-cols-[minmax(240px,0.52fr)_minmax(300px,0.64fr)_minmax(420px,1fr)]">
              <section className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-black uppercase tracking-[0.16em] text-primary">1 目标</div>
                    <h3 className="mt-1 text-base font-black text-on-surface">目标资产桶</h3>
                  </div>
                  <div className="rounded-full border border-outline-variant/16 bg-surface-container-highest px-2 py-0.5 text-[11px] text-on-surface-variant">
                    {items.length} 个
                  </div>
                </div>
                <p className="mt-2 text-xs leading-5 text-on-surface-variant">
                  这里不是逐张出图入口。每个目标会先被理解成意图说明，再放进整图规划的固定格位。
                </p>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="rounded-lg bg-surface-container-highest px-2.5 py-2">
                    <div className="text-[11px] text-outline">目标数</div>
                    <div className="text-lg font-black text-on-surface">{items.length}</div>
                  </div>
                  <div className="rounded-lg bg-surface-container-highest px-2.5 py-2">
                    <div className="text-[11px] text-outline">意图说明</div>
                    <div className="text-lg font-black text-on-surface">
                      {selectedSheet ? `${selectedSheetBriefsReady}/${selectedSheetBoundSlots}` : '未规划'}
                    </div>
                  </div>
                  <div className="rounded-lg bg-surface-container-highest px-2.5 py-2">
                    <div className="text-[11px] text-outline">已出候选</div>
                    <div className="text-lg font-black text-on-surface">{generatedItems}</div>
                  </div>
                  <div className="rounded-lg bg-surface-container-highest px-2.5 py-2">
                    <div className="text-[11px] text-outline">星标图</div>
                    <div className="text-lg font-black text-primary">{metrics?.starred_images ?? 0}</div>
                  </div>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    onClick={() => setModal('bulk')}
                    className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container-high"
                  >
                    导入目标
                  </button>
                  <button
                    onClick={() => {
                      resetSingleDraft()
                      setModal('single')
                    }}
                    className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container-high"
                  >
                    新增目标
                  </button>
                </div>
                <div className="mt-3 grid max-h-64 gap-1.5 overflow-auto pr-1">
                  {items.slice(0, 12).map((item) => (
                    <button
                      key={item.item_id}
                      type="button"
                      onClick={() => onSelectItem(item.item_id)}
                      className={clsx(
                        'grid grid-cols-[minmax(0,1fr)_auto] gap-2 rounded-lg px-2.5 py-2 text-left transition-colors hover:bg-surface-container-high',
                        activeItemId === item.item_id ? 'bg-primary/12' : 'bg-surface-container-highest',
                      )}
                    >
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-bold text-on-surface">
                          {item.title || item.item_id}
                        </span>
                        <span className="mt-0.5 block truncate text-[11px] text-on-surface-variant">
                          {item.description || item.extra_context || item.item_id}
                        </span>
                      </span>
                      <span className={clsx('rounded-full border px-2 py-0.5 text-[10px] font-bold', statusBadge(item.status))}>
                        {statusLabel(item.status)}
                      </span>
                    </button>
                  ))}
                  {items.length > 12 ? (
                    <div className="px-2 py-1 text-[11px] text-on-surface-variant">
                      还有 {items.length - 12} 个目标在下方目标概览中。
                    </div>
                  ) : null}
                </div>
              </section>

              <section className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-[11px] font-black uppercase tracking-[0.16em] text-secondary">2 整图记录</div>
                    <h3 className="mt-1 text-base font-black text-on-surface">整图生成</h3>
                  </div>
                  {sheets.length > 0 ? (
                    <select
                      value={selectedSheet?.sheet_id ?? ''}
                      onChange={(event) =>
                        setSheetSelection({ taskId: task.task_id, sheetId: event.target.value || null })
                      }
                      className="max-w-[190px] rounded-xl border border-outline-variant/20 bg-surface-container-highest px-3 py-2 text-xs font-bold text-on-surface outline-none"
                      aria-label="选择整图记录"
                    >
                      {sheets.map((sheet) => (
                        <option key={sheet.sheet_id} value={sheet.sheet_id}>
                          {sheet.sheet_id} · {statusLabel(sheet.status)}
                        </option>
                      ))}
                    </select>
                  ) : null}
                </div>
                <p className="mt-2 text-xs leading-5 text-on-surface-variant">
                  先新建整图规划，再提交当前规划出图。想再跑一张，就再新建一张整图；旧图和旧审图不会被删除。
                </p>
                <div className="mt-3">
                  <button
                    type="button"
                    disabled={actionBusy || items.length === 0}
                    onClick={handleCreateSheetRun}
                    className="inline-flex items-center gap-2 rounded-xl border border-primary/35 px-3 py-2 text-xs font-black text-primary transition-colors hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <Icon name="add" className="text-[16px]" />
                    新建下一张整图
                  </button>
                </div>
                {selectedSheet ? (
                  <>
                    <div className="mt-3 grid grid-cols-4 gap-2">
                      <div className="rounded-lg bg-surface-container-highest px-2.5 py-2">
                        <div className="text-[11px] text-outline">状态</div>
                        <div className="truncate text-sm font-black text-on-surface">{statusLabel(selectedSheet.status)}</div>
                      </div>
                      <div className="rounded-lg bg-surface-container-highest px-2.5 py-2">
                        <div className="text-[11px] text-outline">固定目标</div>
                        <div className="text-sm font-black text-on-surface">{selectedSheetBoundSlots}</div>
                      </div>
                      <div className="rounded-lg bg-surface-container-highest px-2.5 py-2">
                        <div className="text-[11px] text-outline">涌现</div>
                        <div className="text-sm font-black text-on-surface">{selectedSheetEmergentSlots}</div>
                      </div>
                      <div className="rounded-lg bg-surface-container-highest px-2.5 py-2">
                        <div className="text-[11px] text-outline">剩余</div>
                        <div className="text-sm font-black text-on-surface">{selectedSheet.input.remaining_item_count ?? 0}</div>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={actionBusy || !canGenerateSheet}
                        onClick={() => void onGridSheetAction('generate', selectedSheet.sheet_id)}
                        className="rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        提交当前整图出图
                      </button>
                      <button
                        type="button"
                        disabled={actionBusy || !canPollSheet}
                        onClick={() => void onGridSheetAction('poll', selectedSheet.sheet_id)}
                        className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        检查生成结果
                      </button>
                      <button
                        type="button"
                        disabled={actionBusy || !canSplitSheet}
                        onClick={() =>
                          void onGridSheetAction('split', selectedSheet.sheet_id, {
                            cropBoxPercent: selectedSheetCrop,
                            xLinesPercent: selectedSheetLines.x,
                            yLinesPercent: selectedSheetLines.y,
                          })
                        }
                        className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        按当前切线重切
                      </button>
                      <button
                        type="button"
                        disabled={actionBusy || !canBackfillSheet}
                        onClick={() => void onGridSheetAction('backfill', selectedSheet.sheet_id)}
                        className="rounded-xl border border-emerald-300/30 px-3 py-2 text-xs font-bold text-emerald-100 transition-colors hover:bg-emerald-300/10 disabled:cursor-not-allowed disabled:opacity-60"
                        title="把当前整图里已经标记为采纳的切片复制进对应目标的候选池，并默认星标。"
                      >
                        入池已采纳切片
                      </button>
                    </div>
                    <div className="mt-3 grid gap-3">
                      <div className="min-w-0 rounded-lg bg-surface-container-highest px-3 py-3">
                        <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                          整图提示词
                        </div>
                        <pre className="mt-2 max-h-44 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-on-surface-variant">
                          {selectedSheetPrompt || '尚未生成提示词'}
                        </pre>
                      </div>
                      <div className="min-w-0 rounded-lg bg-surface-container-highest px-3 py-3">
                        <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                          格位预览
                        </div>
                        <div className="mt-2 grid max-h-40 gap-1.5 overflow-auto">
                          {selectedSheet.slots.slice(0, 16).map((slot) => (
                            <div
                              key={slot.cell_id}
                              className="grid grid-cols-[74px_70px_minmax(0,1fr)] gap-2 rounded-lg bg-surface-container px-2 py-1.5 text-[11px]"
                            >
                              <span className="font-mono text-outline">{slot.cell_id}</span>
                              <span className={slot.kind === 'emergent' ? 'text-amber-200' : 'text-primary'}>
                                {slot.kind === 'emergent' ? '涌现' : '固定'}
                              </span>
                              <span className="truncate text-on-surface-variant">{slot.title || slot.item_id}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="mt-3 rounded-lg bg-surface-container-highest px-3 py-4 text-sm leading-6 text-on-surface-variant">
                    当前还没有整图记录。先补齐批次目标，再点击上方按钮新建第一张整图规划。
                  </div>
                )}
              </section>

            <section className="min-w-0 rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-3">
              <div className="flex flex-col gap-3 border-b border-outline-variant/10 pb-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <div className="text-[11px] font-black uppercase tracking-[0.16em] text-emerald-200">3 切片审图</div>
                  <h3 className="mt-1 text-base font-black text-on-surface">切分审图层</h3>
                  <p className="mt-1 text-xs leading-5 text-on-surface-variant">
                    蓝线是系统真实切分层。只有你采纳的切片会进入目标候选池，并默认星标。
                  </p>
                </div>
                {selectedSheet ? (
                  <div className="grid grid-cols-5 gap-1.5 text-center text-[11px]">
                    <div className="rounded-lg bg-surface-container-highest px-2 py-1.5">
                      <div className="text-outline">待审</div>
                      <div className="font-black text-on-surface">{sheetReviewCounts.pending}</div>
                    </div>
                    <div className="rounded-lg bg-surface-container-highest px-2 py-1.5">
                      <div className="text-outline">采纳</div>
                      <div className="font-black text-emerald-100">{sheetReviewCounts.selected}</div>
                    </div>
                    <div className="rounded-lg bg-surface-container-highest px-2 py-1.5">
                      <div className="text-outline">废弃</div>
                      <div className="font-black text-error">{sheetReviewCounts.rejected}</div>
                    </div>
                    <div className="rounded-lg bg-surface-container-highest px-2 py-1.5">
                      <div className="text-outline">涌现</div>
                      <div className="font-black text-amber-100">{sheetReviewCounts.emergent}</div>
                    </div>
                    <div className="rounded-lg bg-surface-container-highest px-2 py-1.5">
                      <div className="text-outline">入池</div>
                      <div className="font-black text-primary">{sheetReviewCounts.promoted}</div>
                    </div>
                  </div>
                ) : null}
              </div>

              {selectedSheet ? (
                <div className="mt-3 grid gap-3 2xl:grid-cols-[minmax(360px,0.95fr)_minmax(0,1.05fr)]">
                  <div className="min-w-0">
                    {selectedSheet.source_image_url ? (
                      <div className="mb-3 rounded-xl border border-outline-variant/12 bg-surface-container-highest px-3 py-3">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <div className="text-[11px] font-black uppercase tracking-[0.16em] text-sky-200">
                              切线校准
                            </div>
                            <div className="mt-1 text-xs leading-5 text-on-surface-variant">
                              拖动图上的蓝色线可以校准外框和中间切线；下方滑杆用于精调外框。
                            </div>
                          </div>
                          <button
                            type="button"
                            disabled={actionBusy}
                            onClick={resetSelectedSheetLines}
                            className="rounded-lg border border-outline-variant/20 px-2.5 py-1.5 text-[11px] font-bold text-on-surface transition-colors hover:bg-surface-container disabled:opacity-60"
                          >
                            重置全图
                          </button>
                        </div>
                        <div className="mt-3 grid gap-2 sm:grid-cols-2">
                          {([
                            ['x', 0, '左边', 0, Math.min(95, selectedSheetCrop.right - 5)],
                            [
                              'x',
                              selectedSheetLines.x.length - 1,
                              '右边',
                              Math.max(5, selectedSheetCrop.left + 5),
                              100,
                            ],
                            ['y', 0, '上边', 0, Math.min(95, selectedSheetCrop.bottom - 5)],
                            [
                              'y',
                              selectedSheetLines.y.length - 1,
                              '下边',
                              Math.max(5, selectedSheetCrop.top + 5),
                              100,
                            ],
                          ] as Array<['x' | 'y', number, string, number, number]>).map(([axis, index, label, min, max]) => {
                            const value =
                              axis === 'x'
                                ? selectedSheetLines.x[index]
                                : selectedSheetLines.y[index]
                            return (
                              <label key={`${axis}-${index}`} className="grid gap-1 text-[11px] font-bold text-on-surface-variant">
                                <span className="flex items-center justify-between">
                                  <span>{label}</span>
                                  <span className="font-mono text-outline">
                                    {Math.round(value)}%
                                  </span>
                                </span>
                                <input
                                  type="range"
                                  min={min}
                                  max={max}
                                  step={0.1}
                                  value={value}
                                  onChange={(event) =>
                                    updateSelectedSheetLine(axis, index, Number(event.target.value))
                                  }
                                  className="w-full accent-primary"
                                />
                              </label>
                            )
                          })}
                        </div>
                      </div>
                    ) : null}
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
                            className="absolute inset-0 touch-none"
                            onPointerMove={handleCutLinePointerMove}
                            onPointerUp={() => setDragLine(null)}
                            onPointerCancel={() => setDragLine(null)}
                          >
                            <div
                              className="pointer-events-none absolute border-2 border-sky-300/90 shadow-[0_0_0_9999px_rgba(2,132,199,0.12)]"
                              style={cropBoxStyle(selectedSheetCrop)}
                            />
                            {selectedSheet.tiles.map((tile) => {
                              const isActive = selectedTile?.cell_id === tile.cell_id
                              return (
                                <button
                                  key={tile.cell_id}
                                  type="button"
                                  title={`${tile.cell_id} · ${reviewLabel(tile.review_status)}`}
                                  onClick={() => setSelectedTileCellId(tile.cell_id)}
                                  style={cellBoxStyle(selectedSheetLines, tile.row, tile.col)}
                                  className={clsx(
                                    'group absolute z-10 border border-sky-300/60 bg-sky-300/0 transition-colors hover:bg-sky-300/12',
                                    isActive && 'z-20 border-2 border-primary bg-primary/10',
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
                            {selectedSheetLines.x.map((left, index) => (
                              <button
                                key={`x-${index}`}
                                type="button"
                                aria-label={`拖动第 ${index} 条纵向切线`}
                                title={`纵向切线 ${index}: ${left.toFixed(1)}%`}
                                onPointerDown={(event) => handleCutLinePointerDown(event, 'x', index)}
                                className={clsx(
                                  'absolute z-30 -translate-x-1/2 cursor-ew-resize rounded-full border border-sky-100/80 bg-sky-300/85 shadow-[0_0_12px_rgba(56,189,248,0.45)] transition-colors hover:bg-primary',
                                  index === 0 || index === selectedSheetLines.x.length - 1 ? 'w-3' : 'w-2',
                                )}
                                style={{
                                  left: `${left}%`,
                                  top: `${selectedSheetCrop.top}%`,
                                  height: `${selectedSheetCrop.bottom - selectedSheetCrop.top}%`,
                                }}
                              />
                            ))}
                            {selectedSheetLines.y.map((top, index) => (
                              <button
                                key={`y-${index}`}
                                type="button"
                                aria-label={`拖动第 ${index} 条横向切线`}
                                title={`横向切线 ${index}: ${top.toFixed(1)}%`}
                                onPointerDown={(event) => handleCutLinePointerDown(event, 'y', index)}
                                className={clsx(
                                  'absolute z-30 -translate-y-1/2 cursor-ns-resize rounded-full border border-sky-100/80 bg-sky-300/85 shadow-[0_0_12px_rgba(56,189,248,0.45)] transition-colors hover:bg-primary',
                                  index === 0 || index === selectedSheetLines.y.length - 1 ? 'h-3' : 'h-2',
                                )}
                                style={{
                                  top: `${top}%`,
                                  left: `${selectedSheetCrop.left}%`,
                                  width: `${selectedSheetCrop.right - selectedSheetCrop.left}%`,
                                }}
                              />
                            ))}
                          </div>
                        </>
                      ) : selectedSheetGenerating ? (
                        <div className="flex h-full w-full flex-col items-center justify-center gap-3 px-6 text-center">
                          <div className="flex h-14 w-14 items-center justify-center rounded-full border border-primary/25 bg-primary/10">
                            <div className="h-7 w-7 animate-spin rounded-full border-2 border-primary border-t-transparent" />
                          </div>
                          <div>
                            <div className="text-sm font-black text-on-surface">整图正在生成中</div>
                            <div className="mt-1 text-xs leading-5 text-on-surface-variant">
                              已提交到图片服务，等待生成结果。这里不展示假进度，只提示任务还在跑。
                            </div>
                          </div>
                          {selectedSheet.async_job?.task_id ? (
                            <div className="max-w-full truncate rounded-full border border-outline-variant/16 bg-surface-container px-2.5 py-1 font-mono text-[10px] text-outline">
                              {selectedSheet.async_job.task_id}
                            </div>
                          ) : null}
                        </div>
                      ) : (
                        <div className="flex h-full w-full flex-col items-center justify-center gap-2 text-center">
                          <Icon name="image" className="text-[34px] text-outline" />
                          <div className="text-xs text-on-surface-variant">等待整张图生成</div>
                        </div>
                      )}
                    </div>

                    {selectedSheet.tiles.length > 0 ? (
                      <div className="mt-3 grid max-h-64 grid-cols-6 gap-1.5 overflow-auto pr-1 md:grid-cols-8 xl:grid-cols-6 2xl:grid-cols-8">
                        {selectedSheet.tiles.map((tile) => {
                          const toneDot =
                            tile.review_status === 'selected'
                              ? 'bg-emerald-300'
                              : tile.review_status === 'rejected'
                                ? 'bg-error'
                                : tile.review_status === 'emergent'
                                  ? 'bg-amber-300'
                                  : 'bg-sky-300'
                          return (
                            <button
                              key={tile.cell_id}
                              type="button"
                              onClick={() => setSelectedTileCellId(tile.cell_id)}
                              className={clsx(
                                'group overflow-hidden rounded-lg border bg-surface-container-highest text-left transition-colors hover:border-primary/50',
                                selectedTile?.cell_id === tile.cell_id ? 'border-primary' : 'border-outline-variant/12',
                              )}
                              title={`${tile.cell_id} · ${reviewLabel(tile.review_status)}`}
                            >
                              {tile.image_url ? (
                                <img src={tile.image_url} alt={tile.cell_id} className="aspect-square w-full object-cover" />
                              ) : (
                                <div className="flex aspect-square items-center justify-center">
                                  <Icon name="image" className="text-[18px] text-outline" />
                                </div>
                              )}
                              <div className="flex items-center justify-between gap-1 px-1.5 py-1">
                                <span className="truncate font-mono text-[10px] text-outline">{tile.cell_id}</span>
                                <span className={clsx('h-2 w-2 rounded-full', toneDot)} />
                              </div>
                            </button>
                          )
                        })}
                      </div>
                    ) : null}
                  </div>

                  <div className="min-w-0">
                    {selectedTile ? (
                      <div className="grid gap-3">
                        <div className="grid gap-3 md:grid-cols-[180px_minmax(0,1fr)]">
                          <div className="overflow-hidden rounded-xl border border-outline-variant/12 bg-surface-container-highest">
                            {selectedTile.image_url ? (
                              <img src={selectedTile.image_url} alt={selectedTile.cell_id} className="aspect-square w-full object-cover" />
                            ) : (
                              <div className="flex aspect-square items-center justify-center">
                                <Icon name="image" className="text-[28px] text-outline" />
                              </div>
                            )}
                          </div>
                          <div className="min-w-0 rounded-xl bg-surface-container-highest px-3 py-3">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-mono text-sm font-black text-on-surface">{selectedTile.cell_id}</span>
                              <span className={clsx('rounded-full border px-2 py-0.5 text-[11px] font-bold', reviewTone(selectedTile.review_status))}>
                                {reviewLabel(selectedTile.review_status)}
                              </span>
                              <span className="rounded-full border border-outline-variant/16 px-2 py-0.5 text-[11px] text-on-surface-variant">
                                {selectedTileSlot?.kind === 'emergent' ? '涌现格位' : '固定目标格位'}
                              </span>
                              {selectedTile.promoted_version ? (
                                <span className="rounded-full border border-emerald-300/35 bg-emerald-300/12 px-2 py-0.5 text-[11px] font-bold text-emerald-100">
                                  已入池并星标
                                </span>
                              ) : null}
                            </div>
                            <div className="mt-3 text-xs leading-5 text-on-surface-variant">
                              <div>规划标题：{selectedTileSlot?.title || selectedTile.item_id || '未命名槽位'}</div>
                              <div>当前绑定：{selectedTileLinkedItem?.title || selectedTileTarget || '未绑定目标'}</div>
                            </div>
                            <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
                              <select
                                value={selectedTileTarget}
                                onChange={(event) =>
                                  setTileTargets((current) => ({ ...current, [selectedTile.cell_id]: event.target.value }))
                                }
                                className="min-w-0 rounded-xl border border-outline-variant/20 bg-surface-container px-3 py-2 text-xs font-bold text-on-surface outline-none"
                              >
                                <option value="">未绑定目标</option>
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
                                onClick={() => void onGridSheetTileAction('pending', selectedSheet.sheet_id, selectedTile.cell_id)}
                                className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:opacity-60"
                              >
                                退回待审
                              </button>
                              <button
                                type="button"
                                disabled={actionBusy}
                                onClick={() => void onGridSheetTileAction('rejected', selectedSheet.sheet_id, selectedTile.cell_id)}
                                className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:opacity-60"
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
                                className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container disabled:opacity-60"
                              >
                                创建目标并采纳
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-xl bg-surface-container-highest px-4 py-5 text-sm leading-6 text-on-surface-variant">
                        切图后选择一个切片，就能在这里做采纳、废弃、绑定目标或创建新目标。
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="mt-3 rounded-xl bg-surface-container-highest px-4 py-8 text-center text-sm leading-6 text-on-surface-variant">
                  还没有整图记录。先在左侧确认目标，再新建第一张整图规划。
                </div>
              )}
            </section>
          </div>
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-outline-variant/12 bg-surface-container-low">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-outline-variant/10 px-4 py-3">
          <div className="flex items-center gap-2">
            <Icon name="view_list" className="text-[18px] text-primary" />
            <span className="text-sm font-bold text-on-surface">目标概览</span>
            <span className="text-xs text-on-surface-variant">在一个屏幕里快速浏览状态和版本</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setModal('bulk')}
              className="rounded-xl border border-outline-variant/20 px-3 py-2 text-xs font-bold text-on-surface transition-colors hover:bg-surface-container"
            >
              批量导入
            </button>
            <button
              onClick={() => {
                resetSingleDraft()
                setModal('single')
              }}
              className="flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim"
            >
              <Icon name="add" className="text-[16px]" />
              新增目标
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
              {actionBusy ? '处理中…' : '导出星标压缩包'}
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
              {actionBusy ? '执行中…' : '自动跑完整批次'}
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
                <th className="px-4 py-2.5">目标</th>
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
            <p className="text-sm text-on-surface-variant">当前批次还没有目标</p>
            <p className="mt-2 text-xs text-outline">可以先新增目标，也可以一次性导入 CSV 或表格数据。</p>
          </div>
        ) : null}
      </section>

      {modal === 'single' ? (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 p-6 backdrop-blur-sm">
          <button
            type="button"
            className="absolute inset-0"
            aria-label="关闭新增目标"
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
                    新增目标
                  </div>
                  <h3 className="mt-2 text-[1.7rem] font-black tracking-tight text-on-surface">
                    新增目标
                  </h3>
                  <p className="mt-2 max-w-xl text-sm leading-6 text-on-surface-variant">
                    一个目标就是一个具体要做的图标。先把名称和需求说清楚，再决定它属于什么类型。
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
                      <div className="text-xs font-bold text-on-surface">目标名称</div>
                      <div className="mt-1 leading-6">这个图标的名字，例如“雷暴”“治疗术”“火球”。</div>
                    </div>
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">资产类型</div>
                      <div className="mt-1 leading-6">更偏技术上的归类，主要帮助后面统一管理和扩展。</div>
                    </div>
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">标签分类</div>
                      <div className="mt-1 leading-6">更偏业务上的分组，比如战斗、辅助、资源。后面筛选会用到。</div>
                    </div>
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">目标描述</div>
                      <div className="mt-1 leading-6">直接写用户需求，越具体越好。</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-6">
                <div className="space-y-4">
                  <label className="block">
                    <span className="mb-2 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                      目标名称
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
                          资产类型
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
                          placeholder="输入你自己的资产类型，例如 hero_icon"
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
                        目标描述
                      </span>
                      <span className="text-[11px] text-outline">真正的用户需求</span>
                    </div>
                    <textarea
                      value={description}
                      onChange={(event) => setDescription(event.target.value)}
                      className="min-h-28 w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm leading-6 text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                      placeholder="直接写这个图标要表达什么、长什么样、重点突出什么。"
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
                      placeholder="比如颜色偏好、参考元素、禁用元素、和同批次其他图标的关系。"
                    />
                  </label>
                </div>

                <div className="mt-6 flex items-center justify-between gap-3">
                  <div className="text-xs text-on-surface-variant">
                    创建后可以继续编辑，也可以批量再导入更多目标。
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
                      {actionBusy ? '创建中…' : '创建目标'}
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
                <h3 className="text-lg font-bold text-on-surface">批量导入目标</h3>
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
                  CSV 是逗号分隔；TSV 是制表符分隔，更适合直接从 Excel 或飞书表格复制粘贴。
                </div>
                <div className="mt-2 text-xs leading-5 text-outline">
                  推荐先下载模板填充，再导入；也可以直接把 Excel 或飞书表格内容复制后粘贴到右侧文本框。
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
                {actionBusy ? '导入中…' : '导入目标'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
