import clsx from 'clsx'
import { useState } from 'react'
import type { ItemSummary, TaskSummary } from '../types'
import { parseImportedItems } from '../lib/itemImport'
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

const clampTwoLinesStyle = {
  display: '-webkit-box',
  WebkitBoxOrient: 'vertical' as const,
  WebkitLineClamp: 2,
  overflow: 'hidden',
}

function descriptionFallback(task: TaskSummary) {
  if (task.project_background) return task.project_background
  if (task.style_requirements) return `风格要求：${task.style_requirements}`
  return '这个批次还没有填写项目背景和统一风格要求。'
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
  activeItemId,
  onSelectItem,
  onSaveTaskSettings,
  onRunBatchPipeline,
  onExportStarredImages,
  onCreateItem,
  onCreateItemsBulk,
  actionBusy,
  actionError,
}: {
  task: TaskSummary
  items: ItemSummary[]
  activeItemId: string | null
  onSelectItem: (itemId: string) => void
  onSaveTaskSettings: (payload: {
    task_name: string
    project_background: string
    style_requirements: string
    asset_domain: string
    image_aspect_ratio: string
    image_resolution: string
  }) => Promise<void>
  onRunBatchPipeline: (options?: { autoApprove?: boolean }) => Promise<void>
  onExportStarredImages: () => Promise<void>
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
  const [bulkText, setBulkText] = useState('')
  const [bulkSummary, setBulkSummary] = useState<string | null>(null)

  const completed = task.items_summary?.completed ?? 0
  const inProgress = task.items_summary?.in_progress ?? 0
  const draft = task.items_summary?.draft ?? 0
  const totalPendingJobs = items.reduce((sum, item) => sum + (item.pending_image_jobs ?? 0), 0)

  function resetTaskSettingsDraft() {
    setTaskName(task.task_name)
    setProjectBackground(task.project_background)
    setStyleRequirements(task.style_requirements)
    setAssetDomain(task.asset_domain)
    setImageAspectRatio(task.runtime_config?.image_aspect_ratio || '1:1')
    setImageResolution(task.runtime_config?.image_resolution || '1K')
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
                <p
                  className="mt-1 text-xs leading-5 text-on-surface-variant"
                  style={clampTwoLinesStyle}
                >
                  {task.project_background || '未填写'}
                </p>
              </div>
              <div className="min-w-0 rounded-lg border border-outline-variant/12 bg-surface-container px-3 py-2.5">
                <div className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                  统一风格要求
                </div>
                <p
                  className="mt-1 text-xs leading-5 text-on-surface-variant"
                  style={clampTwoLinesStyle}
                >
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
                              'text-[0.98rem] font-black leading-5 transition-colors group-hover:text-primary',
                              isActive ? 'text-primary' : 'text-on-surface',
                            )}
                            style={clampTwoLinesStyle}
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
                        <div
                          className="mt-2 text-[0.82rem] leading-5 text-on-surface-variant"
                          style={clampTwoLinesStyle}
                        >
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
                <div className="mt-3 text-xs leading-5 text-on-surface-variant">
                  也可以直接把 Excel / 飞书表格内容复制后粘贴到右侧文本框。
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
