import { useEffect, useMemo, useState } from 'react'
import clsx from 'clsx'
import {
  Activity,
  Bell,
  Bot,
  ChevronRight,
  Clock3,
  FileText,
  FolderOpen,
  FolderPlus,
  Image as ImageIcon,
  LayoutGrid,
  MessageSquareText,
  Search,
  Settings,
  Sparkles,
  WandSparkles,
} from 'lucide-react'

import {
  fetchProviders,
  fetchTask,
  fetchTaskItem,
  fetchTaskItems,
  fetchTaskItemWorkspace,
  fetchTasks,
} from './lib/api'
import type {
  ArtifactSnapshot,
  CandidateVersion,
  ItemSummary,
  ProviderSummary,
  TaskSummary,
  WorkspacePayload,
} from './types'

type WorkspaceTab = 'batch' | 'item'
type OutputTab = 'overview' | 'brief' | 'prompt' | 'candidate'

const stageLabelMap: Record<string, string> = {
  draft: '待开始',
  brief_generated: '待确认设计说明',
  brief_approved: '设计说明已确认',
  prompt_generated: '待确认出图指令',
  prompt_approved: '可生成候选图',
  image_generating: '候选图生成中',
  image_generated: '待选择候选图',
  completed: '已完成',
  failed: '失败',
  archived: '已归档',
}

const stageToneMap: Record<
  string,
  'neutral' | 'primary' | 'success' | 'warning' | 'danger'
> = {
  draft: 'neutral',
  brief_generated: 'warning',
  brief_approved: 'primary',
  prompt_generated: 'warning',
  prompt_approved: 'primary',
  image_generating: 'primary',
  image_generated: 'warning',
  completed: 'success',
  failed: 'danger',
  archived: 'neutral',
}

function formatRelativeDate(value: string | null | undefined) {
  if (!value) return '暂无'
  try {
    return new Intl.DateTimeFormat('zh-CN', {
      month: 'numeric',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  } catch {
    return value
  }
}

function statusLabel(status: string) {
  return stageLabelMap[status] ?? status
}

function stageTone(status: string) {
  return stageToneMap[status] ?? 'neutral'
}

function modelLabel(value: string | null | undefined) {
  if (!value) return '继承默认'
  return value.replace(/^models\//, '')
}

function outputRecord(snapshot: ArtifactSnapshot | null) {
  return (snapshot?.output ?? {}) as Record<string, unknown>
}

function inputRecord(snapshot: ArtifactSnapshot | null) {
  return (snapshot?.input ?? {}) as Record<string, unknown>
}

function stringList(value: unknown) {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string')
}

function itemCurrentVersion(item: ItemSummary) {
  return (
    item.current_versions.image_generation ||
    item.current_versions.image_prompt ||
    item.current_versions.brief_generation ||
    '暂无版本'
  )
}

function recommendedAction(status: string) {
  switch (status) {
    case 'draft':
      return '生成设计说明'
    case 'brief_generated':
      return '确认设计说明'
    case 'brief_approved':
      return '生成出图指令'
    case 'prompt_generated':
      return '确认出图指令'
    case 'prompt_approved':
      return '生成候选图'
    case 'image_generating':
      return '等待候选图'
    case 'image_generated':
      return '选择候选图'
    case 'completed':
      return '查看结果'
    case 'failed':
      return '重试或回退'
    default:
      return '继续处理'
  }
}

function Pill({ status }: { status: string }) {
  const tone = stageTone(status)
  const classes = {
    neutral: 'bg-white/6 text-text-soft',
    primary: 'bg-primary/14 text-primary',
    success: 'bg-emerald-400/14 text-emerald-300',
    warning: 'bg-amber-400/14 text-amber-300',
    danger: 'bg-rose-400/14 text-rose-300',
  }[tone]

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold tracking-wide',
        classes,
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {statusLabel(status)}
    </span>
  )
}

function SummaryMetric({
  label,
  value,
}: {
  label: string
  value: string | number
}) {
  return (
    <div className="rounded-3xl border border-white/8 bg-surface p-5 shadow-lg shadow-black/10">
      <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.2em] text-text-soft">
        {label}
      </p>
      <p className="text-3xl font-black tracking-tight text-white">{value}</p>
    </div>
  )
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex min-h-[420px] flex-col items-center justify-center rounded-[28px] border border-dashed border-white/10 bg-surface p-10 text-center">
      <LayoutGrid className="mb-4 h-10 w-10 text-text-soft" />
      <h3 className="mb-3 text-2xl font-bold text-white">{title}</h3>
      <p className="max-w-lg text-sm leading-7 text-text-soft">{body}</p>
    </div>
  )
}

function Sidebar({
  tasks,
  activeTaskId,
  onSelectTask,
  onOpenSettings,
}: {
  tasks: TaskSummary[]
  activeTaskId: string | null
  onSelectTask: (taskId: string) => void
  onOpenSettings: () => void
}) {
  const activeTask = tasks.find((task) => task.task_id === activeTaskId) ?? null
  const historicalTasks = tasks.filter((task) => task.task_id !== activeTaskId)

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col border-r border-white/8 bg-surface-low">
      <div className="border-b border-white/8 px-6 py-6">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-black">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-white">项目资产</h2>
            <p className="text-[11px] uppercase tracking-[0.18em] text-text-soft">
              Icon Workbench
            </p>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col px-4 py-5">
        <nav className="mb-6 space-y-1">
          <div className="flex items-center gap-3 rounded-md border-l-2 border-primary bg-surface-high px-3 py-2.5 text-white">
            <FolderOpen className="h-4 w-4" />
            <span className="text-xs font-medium uppercase tracking-[0.16em]">批次</span>
          </div>
        </nav>

        <div className="mb-2 px-1">
          <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-text-soft">
            当前批次
          </span>
        </div>

        {activeTask ? (
          <button
            className="mb-5 rounded-xl border-l-2 border-primary bg-surface px-3 py-3 text-left"
            onClick={() => onSelectTask(activeTask.task_id)}
          >
            <div className="mb-2 flex items-center justify-between gap-2">
              <span className="truncate text-sm font-semibold text-white">
                {activeTask.task_name}
              </span>
              <span className="h-2 w-2 shrink-0 rounded-full bg-primary animate-pulse" />
            </div>
            <p className="text-xs text-text-soft">{statusLabel(activeTask.status)}</p>
          </button>
        ) : null}

        <div className="mb-2 px-1">
          <span className="text-[10px] font-bold uppercase tracking-[0.22em] text-text-soft">
            历史批次
          </span>
        </div>

        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
          {historicalTasks.map((task) => (
            <button
              key={task.task_id}
              className="w-full rounded-md px-3 py-2 text-left text-sm text-text-soft transition hover:bg-surface hover:text-white"
              onClick={() => onSelectTask(task.task_id)}
            >
              <div className="truncate">{task.task_name}</div>
              <div className="mt-1 text-[11px] text-text-soft">
                {statusLabel(task.status)}
              </div>
            </button>
          ))}
        </div>

        <div className="mt-5 border-t border-white/8 pt-5">
          <button className="mb-4 flex w-full items-center justify-center gap-2 rounded-md bg-linear-to-br from-primary to-primary-strong px-4 py-3 text-xs font-bold uppercase tracking-[0.18em] text-black shadow-lg shadow-primary/20">
            <FolderPlus className="h-4 w-4" />
            新建批次
          </button>
          <button
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm text-text-soft transition hover:bg-surface hover:text-white"
            onClick={onOpenSettings}
          >
            <Settings className="h-4 w-4" />
            <span className="text-xs font-medium uppercase tracking-[0.16em]">
              设置
            </span>
          </button>
        </div>
      </div>
    </aside>
  )
}

function ProvidersModal({
  open,
  providers,
  onClose,
}: {
  open: boolean
  providers: ProviderSummary[]
  onClose: () => void
}) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6 backdrop-blur-sm">
      <div className="max-h-[86vh] w-full max-w-5xl overflow-hidden rounded-[28px] border border-white/10 bg-surface shadow-2xl shadow-black/40">
        <div className="flex items-center justify-between border-b border-white/8 px-7 py-5">
          <div>
            <h2 className="text-2xl font-bold text-white">全局设置</h2>
            <p className="mt-1 text-sm text-text-soft">
              管理 provider、多实例配置，以及后续模型继承的全局默认来源。
            </p>
          </div>
          <button
            className="rounded-xl border border-white/10 px-4 py-2 text-sm text-white hover:bg-white/[0.04]"
            onClick={onClose}
          >
            关闭
          </button>
        </div>

        <div className="grid gap-6 overflow-y-auto p-7 lg:grid-cols-[1.2fr_1fr]">
          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-white">Provider 配置</h3>
                <p className="mt-1 text-sm text-text-soft">
                  内置与第三方实例会在这里统一管理。
                </p>
              </div>
              <button className="rounded-lg bg-primary/14 px-3 py-2 text-xs font-semibold text-primary">
                新增实例
              </button>
            </div>
            <div className="space-y-3">
              {providers.map((provider) => (
                <div
                  key={provider.id}
                  className="rounded-2xl border border-white/8 bg-surface p-4"
                >
                  <div className="mb-3 flex items-start justify-between gap-4">
                    <div>
                      <h4 className="text-base font-semibold text-white">
                        {provider.label}
                      </h4>
                      <p className="mt-1 text-xs uppercase tracking-[0.16em] text-text-soft">
                        {provider.provider_type}
                      </p>
                    </div>
                    <span
                      className={clsx(
                        'rounded-full px-3 py-1 text-[11px] font-semibold',
                        provider.builtin
                          ? 'bg-primary/14 text-primary'
                          : 'bg-white/8 text-text-soft',
                      )}
                    >
                      {provider.builtin ? '内置' : '第三方'}
                    </span>
                  </div>
                  <div className="grid gap-3 text-sm sm:grid-cols-2">
                    <div>
                      <p className="mb-1 text-text-soft">Base URL</p>
                      <p className="truncate text-white">
                        {provider.base_url || '本地 / 无需 URL'}
                      </p>
                    </div>
                    <div>
                      <p className="mb-1 text-text-soft">模型数量</p>
                      <p className="text-white">{provider.model_count}</p>
                    </div>
                    <div>
                      <p className="mb-1 text-text-soft">最近同步</p>
                      <p className="text-white">
                        {provider.last_synced_at
                          ? formatRelativeDate(provider.last_synced_at)
                          : '尚未同步'}
                      </p>
                    </div>
                    <div>
                      <p className="mb-1 text-text-soft">最近错误</p>
                      <p className="text-white">{provider.last_error || '无'}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-[24px] border border-white/8 bg-white/[0.03] p-5">
            <div className="mb-5">
              <h3 className="text-lg font-semibold text-white">系统模板</h3>
              <p className="mt-1 text-sm text-text-soft">
                这里用于管理设计说明模板和出图指令模板。
              </p>
            </div>
            <div className="space-y-4">
              <div className="rounded-2xl border border-white/8 bg-surface p-4">
                <p className="mb-2 text-sm font-semibold text-white">设计说明模板</p>
                <p className="text-sm leading-6 text-text-soft">
                  控制文本 LLM 如何把原始条目输入整理成可审核的设计说明。
                </p>
              </div>
              <div className="rounded-2xl border border-white/8 bg-surface p-4">
                <p className="mb-2 text-sm font-semibold text-white">出图指令模板</p>
                <p className="text-sm leading-6 text-text-soft">
                  控制文本 LLM 如何从设计说明生成最终给图片模型使用的 prompt。
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}

function CandidateVersionCard({ version }: { version: CandidateVersion }) {
  const firstImage = version.candidates[0]?.image_url
  const asyncStatus = version.async_job?.status
  const progress = Number(version.async_job?.progress ?? 0)

  return (
    <article className="overflow-hidden rounded-2xl border border-white/8 bg-surface-high">
      <div className="flex items-center justify-between border-b border-white/8 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-white">
            第 {Number(version.version.replace(/^v/, '')) || version.version} 次生成
          </p>
          <p className="mt-1 text-xs text-text-soft">
            {modelLabel(version.model)} · {formatRelativeDate(version.created_at)}
          </p>
        </div>
        {version.is_current ? (
          <span className="rounded-full bg-primary/14 px-3 py-1 text-[11px] font-semibold text-primary">
            当前采用
          </span>
        ) : null}
      </div>

      {firstImage ? (
        <img
          src={firstImage}
          alt={version.version}
          className="aspect-square w-full object-cover"
        />
      ) : asyncStatus ? (
        <div className="flex aspect-square flex-col items-center justify-center gap-4 bg-primary/6">
          <div className="relative flex h-20 w-20 items-center justify-center rounded-full border border-primary/20">
            <Activity className="h-8 w-8 animate-spin text-primary" />
          </div>
          <div className="text-center">
            <p className="text-sm font-semibold text-white">
              {asyncStatus === 'queued' || asyncStatus === 'pending'
                ? '排队中'
                : asyncStatus === 'failed'
                  ? '生成失败'
                  : '生成中'}
            </p>
            <p className="mt-1 text-xs text-text-soft">
              进度 {Number.isFinite(progress) ? progress : 0}%
            </p>
          </div>
        </div>
      ) : (
        <div className="flex aspect-square items-center justify-center bg-surface-low text-text-soft">
          暂无图片
        </div>
      )}
    </article>
  )
}

function App() {
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null)
  const [items, setItems] = useState<ItemSummary[]>([])
  const [activeItemId, setActiveItemId] = useState<string | null>(null)
  const [activeItem, setActiveItem] = useState<ItemSummary | null>(null)
  const [workspace, setWorkspace] = useState<WorkspacePayload | null>(null)
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>('batch')
  const [outputTab, setOutputTab] = useState<OutputTab>('overview')
  const [providers, setProviders] = useState<ProviderSummary[]>([])
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function bootstrap() {
      setLoading(true)
      setError(null)
      try {
        const [taskRows, providerRows] = await Promise.all([
          fetchTasks(),
          fetchProviders(),
        ])
        setTasks(taskRows)
        setProviders(providerRows)
        if (taskRows.length > 0) {
          setActiveTaskId((current) => current ?? taskRows[0].task_id)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : '加载失败')
      } finally {
        setLoading(false)
      }
    }

    void bootstrap()
  }, [])

  useEffect(() => {
    if (!activeTaskId) return
    const taskId = activeTaskId

    async function loadTaskData() {
      try {
        const [task, itemRows] = await Promise.all([
          fetchTask(taskId),
          fetchTaskItems(taskId),
        ])
        setActiveTask(task)
        setItems(itemRows)
        setActiveItemId((current) => {
          if (current && itemRows.some((row) => row.item_id === current)) return current
          return itemRows[0]?.item_id ?? null
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : '读取批次失败')
      }
    }

    void loadTaskData()
  }, [activeTaskId])

  useEffect(() => {
    if (!activeTaskId || !activeItemId) {
      setActiveItem(null)
      setWorkspace(null)
      return
    }
    const taskId = activeTaskId
    const itemId = activeItemId

    async function loadItemData() {
      try {
        const [item, workspacePayload] = await Promise.all([
          fetchTaskItem(taskId, itemId),
          fetchTaskItemWorkspace(taskId, itemId),
        ])
        setActiveItem(item)
        setWorkspace(workspacePayload)
      } catch (err) {
        setError(err instanceof Error ? err.message : '读取条目失败')
      }
    }

    void loadItemData()
  }, [activeTaskId, activeItemId])

  const summaryCards = useMemo(() => {
    if (!activeTask) return []
    const completed = activeTask.items_summary?.completed ?? 0
    const draft = activeTask.items_summary?.draft ?? 0
    const inProgress = activeTask.items_summary?.in_progress ?? 0
    return [
      { label: '总条目', value: activeTask.item_count },
      { label: '已完成', value: completed },
      { label: '处理中', value: draft + inProgress },
      { label: '批次状态', value: statusLabel(activeTask.status) },
    ]
  }, [activeTask])

  const activeImageModel =
    activeItem?.model_overrides.image_generation.model ??
    activeTask?.model_overrides.image_generation.model ??
    '继承默认模型'

  const briefOutput = outputRecord(workspace?.brief ?? null)
  const promptOutput = outputRecord(workspace?.prompt ?? null)
  const candidateVersions = workspace?.candidate_pool.versions ?? []
  const selectedCandidateVersion =
    candidateVersions.find((version) => version.is_current) ?? candidateVersions[0] ?? null
  const overviewEntries = [
    {
      label: '当前条目',
      value: activeItem?.title ?? '未选中',
      hint: activeItem?.item_id ?? '请选择一个条目开始工作',
    },
    {
      label: '当前阶段',
      value: activeItem ? statusLabel(activeItem.status) : '暂无',
      hint: activeItem ? recommendedAction(activeItem.status) : '等待选择条目',
    },
    {
      label: '候选图模型',
      value: modelLabel(activeImageModel),
      hint: activeItem?.model_overrides.image_generation.provider || '继承批次 / 全局默认',
    },
  ]

  return (
    <div className="min-h-screen bg-background text-text">
      <Sidebar
        tasks={tasks}
        activeTaskId={activeTaskId}
        onSelectTask={setActiveTaskId}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <main className="ml-64 min-h-screen">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-white/8 bg-surface-low/90 px-8 backdrop-blur-xl">
          <div className="flex items-center gap-5">
            <h1 className="text-lg font-black tracking-tight text-white">
              项目资产工作台
            </h1>
            <div className="h-4 w-px bg-white/10" />
            <nav className="flex items-center gap-5 text-sm">
              <button className="border-b-2 border-primary pb-1 font-semibold text-white">
                工作区
              </button>
              <button className="font-semibold text-text-soft hover:text-white">
                审核
              </button>
              <button className="font-semibold text-text-soft hover:text-white">协作</button>
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <label className="relative hidden md:block">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-soft" />
              <input
                className="w-72 rounded-md border border-white/8 bg-surface-high px-10 py-2 text-sm text-white outline-none placeholder:text-text-soft focus:border-primary/40"
                placeholder="搜索条目..."
              />
            </label>
            <button className="rounded-md p-2 text-text-soft hover:bg-surface hover:text-white">
              <Bell className="h-4 w-4" />
            </button>
            <button className="rounded-md p-2 text-text-soft hover:bg-surface hover:text-white">
              <Bot className="h-4 w-4" />
            </button>
          </div>
        </header>

        <div className="space-y-8 p-8">
          {loading ? (
            <EmptyState
              title="正在加载工作台"
              body="前端骨架已经连上本地 API，正在读取批次、条目和 provider 数据。"
            />
          ) : error ? (
            <EmptyState
              title="读取失败"
              body={`当前无法读取本地 API：${error}。请先启动 ai-icon-pipeline-api，再刷新前端。`}
            />
          ) : !activeTask ? (
            <EmptyState
              title="还没有批次"
              body="等你后面接创建批次动作后，这里会成为新的正式工作台主页。"
            />
          ) : (
            <>
              <section className="relative overflow-hidden rounded-[28px] border border-white/8 bg-surface p-7 shadow-2xl shadow-black/20">
                <div className="pointer-events-none absolute right-6 top-4 opacity-10">
                  <WandSparkles className="h-28 w-28 text-primary" />
                </div>
                <div className="flex flex-col justify-between gap-8 xl:flex-row xl:items-start">
                  <div className="max-w-3xl">
                    <div className="mb-3 flex items-center gap-3">
                      <Pill status={activeTask.status} />
                      <span className="text-xs font-medium text-text-soft">
                        {activeTask.task_id}
                      </span>
                    </div>
                    <h2 className="text-4xl font-black tracking-tight text-white">
                      {activeTask.task_name}
                    </h2>
                    <p className="mt-4 max-w-2xl text-sm leading-7 text-text-soft">
                      {activeTask.project_background ||
                        '当前批次还没有填写项目背景。这里已经接成真实批次设定读取，后面再接编辑能力。'}
                    </p>
                    <div className="mt-6 flex flex-wrap gap-3">
                      <span className="rounded-md border border-white/8 bg-surface-high px-3 py-2 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                        {activeTask.asset_domain}
                      </span>
                      <span className="rounded-md border border-white/8 bg-surface-high px-3 py-2 text-xs text-text-soft">
                        更新于 {formatRelativeDate(activeTask.updated_at)}
                      </span>
                    </div>
                  </div>

                  <div className="grid min-w-[340px] grid-cols-2 gap-4 xl:w-[420px]">
                    <div className="rounded-2xl bg-surface-high p-4">
                      <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-text-soft">
                        项目背景
                      </p>
                      <p className="text-sm font-medium text-white">
                        {activeTask.project_background || '未填写'}
                      </p>
                    </div>
                    <div className="rounded-2xl bg-surface-high p-4">
                      <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-text-soft">
                        统一风格要求
                      </p>
                      <p className="text-sm font-medium text-white">
                        {activeTask.style_requirements || '未填写'}
                      </p>
                    </div>
                  </div>
                </div>
              </section>

              <section className="grid gap-4 md:grid-cols-4">
                {summaryCards.map((card) => (
                  <SummaryMetric key={card.label} label={card.label} value={card.value} />
                ))}
              </section>

              <section className="grid gap-8 xl:grid-cols-[1fr_400px]">
                <div className="rounded-[28px] border border-white/8 bg-surface shadow-xl shadow-black/10">
                  <div className="flex items-center justify-between border-b border-white/8 px-6 py-4">
                    <div className="flex items-center gap-2">
                      <LayoutGrid className="h-5 w-5 text-primary" />
                      <div>
                        <h3 className="text-lg font-bold text-white">批次条目概览</h3>
                        <p className="mt-1 text-sm text-text-soft">
                          这里是进入条目工作台的真实入口。
                        </p>
                      </div>
                    </div>
                    <div className="inline-flex rounded-md bg-surface-high p-1">
                      <button
                        className={clsx(
                          'rounded-md px-3 py-2 text-sm font-medium transition',
                          workspaceTab === 'batch'
                            ? 'bg-primary text-black'
                            : 'text-text-soft hover:text-white',
                        )}
                        onClick={() => setWorkspaceTab('batch')}
                      >
                        批次信息
                      </button>
                      <button
                        className={clsx(
                          'rounded-md px-3 py-2 text-sm font-medium transition',
                          workspaceTab === 'item'
                            ? 'bg-primary text-black'
                            : 'text-text-soft hover:text-white',
                        )}
                        onClick={() => setWorkspaceTab('item')}
                      >
                        条目工作台
                      </button>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="min-w-full text-left">
                      <thead className="border-b border-white/8 bg-surface-low/40 text-[11px] uppercase tracking-[0.18em] text-text-soft">
                        <tr>
                          <th className="px-6 py-3 font-semibold">缩略图</th>
                          <th className="px-6 py-3 font-semibold">标题 & ID</th>
                          <th className="px-6 py-3 font-semibold">当前阶段</th>
                          <th className="px-6 py-3 font-semibold">版本 / 结果</th>
                          <th className="px-6 py-3 font-semibold">推荐动作</th>
                          <th className="px-6 py-3 text-right font-semibold">操作</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/8">
                        {items.map((item) => (
                          <tr
                            key={item.item_id}
                            className={clsx(
                              'transition hover:bg-surface-high/40',
                              item.item_id === activeItemId && 'bg-primary/8',
                            )}
                          >
                            <td className="px-6 py-4">
                              <div className="flex h-12 w-12 items-center justify-center rounded-sm border border-white/8 bg-surface-highest text-primary">
                                <ImageIcon className="h-5 w-5" />
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex flex-col">
                                <span className="text-sm font-bold text-white">
                                  {item.title}
                                </span>
                                <span className="text-[11px] text-text-soft">
                                  {item.item_id}
                                </span>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <Pill status={item.status} />
                            </td>
                            <td className="px-6 py-4 text-sm text-text-soft">
                              {itemCurrentVersion(item)}
                            </td>
                            <td className="px-6 py-4 text-sm text-white">
                              {recommendedAction(item.status)}
                            </td>
                            <td className="px-6 py-4 text-right">
                              <button
                                className="inline-flex items-center gap-2 rounded-md bg-surface-high px-3 py-2 text-sm font-medium text-white hover:bg-surface-highest"
                                onClick={() => {
                                  setActiveItemId(item.item_id)
                                  setWorkspaceTab('item')
                                }}
                              >
                                进入工作台
                                <ChevronRight className="h-4 w-4" />
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <aside className="rounded-[28px] border border-white/8 bg-surface p-6 shadow-xl shadow-black/10">
                  <div className="mb-4 flex items-center gap-2">
                    <FolderOpen className="h-5 w-5 text-primary" />
                    <h3 className="text-lg font-bold text-white">当前上下文</h3>
                  </div>
                  <div className="space-y-4">
                    {overviewEntries.map((entry) => (
                      <div
                        key={entry.label}
                        className="rounded-2xl border border-white/8 bg-surface-high p-4"
                      >
                        <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-text-soft">
                          {entry.label}
                        </p>
                        <p className="text-lg font-semibold text-white">{entry.value}</p>
                        <p className="mt-2 text-sm leading-6 text-text-soft">{entry.hint}</p>
                      </div>
                    ))}
                  </div>
                </aside>
              </section>

              {workspaceTab === 'item' && activeItem && workspace ? (
                <section className="rounded-[28px] border border-white/8 bg-surface shadow-xl shadow-black/10">
                  <div className="flex items-center justify-between border-b border-white/8 px-6 py-4">
                    <div>
                      <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-text-soft">
                        条目工作台
                      </p>
                      <h3 className="mt-1 text-2xl font-black tracking-tight text-white">
                        {activeItem.title}
                      </h3>
                    </div>
                    <Pill status={activeItem.status} />
                  </div>

                  <div className="grid gap-6 p-6 xl:grid-cols-[360px_1fr]">
                    <aside className="space-y-5">
                      <div className="rounded-2xl border border-white/8 bg-surface-high p-5">
                        <h4 className="mb-4 text-sm font-bold uppercase tracking-[0.16em] text-primary">
                          原始需求
                        </h4>
                        <div className="space-y-3 text-sm">
                          <div>
                            <p className="mb-1 text-text-soft">标题</p>
                            <p className="font-semibold text-white">{activeItem.title}</p>
                          </div>
                          <div>
                            <p className="mb-1 text-text-soft">描述</p>
                            <p className="leading-6 text-white">{activeItem.description}</p>
                          </div>
                          <div>
                            <p className="mb-1 text-text-soft">补充说明</p>
                            <p className="leading-6 text-white/90">
                              {activeItem.extra_context || '暂无补充说明'}
                            </p>
                          </div>
                          <div className="grid grid-cols-2 gap-3 pt-2">
                            <div className="rounded-xl border border-white/6 bg-surface p-4">
                              <p className="mb-1 text-text-soft">宽高比</p>
                              <p className="font-semibold text-white">
                                {activeItem.runtime_overrides.image_aspect_ratio || '继承批次'}
                              </p>
                            </div>
                            <div className="rounded-xl border border-white/6 bg-surface p-4">
                              <p className="mb-1 text-text-soft">分辨率</p>
                              <p className="font-semibold text-white">
                                {activeItem.runtime_overrides.image_resolution || '继承批次'}
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>

                      <details
                        open
                        className="rounded-2xl border border-white/8 bg-surface-high p-5"
                      >
                        <summary className="cursor-pointer list-none text-sm font-bold uppercase tracking-[0.16em] text-primary">
                          当前条目模型
                        </summary>
                        <div className="mt-4 space-y-3 text-sm">
                          {(
                            [
                              ['设计说明', activeItem.model_overrides.brief_generation],
                              ['出图指令', activeItem.model_overrides.image_prompt],
                              ['候选图', activeItem.model_overrides.image_generation],
                            ] as const
                          ).map(([label, override]) => (
                            <div
                              key={label}
                              className="rounded-xl border border-white/6 bg-surface p-4"
                            >
                              <p className="mb-1 text-text-soft">{label}</p>
                              <p className="font-semibold text-white">
                                {modelLabel(override.model)}
                              </p>
                              <p className="mt-1 text-xs text-text-soft">
                                {override.provider || '未设置 provider 覆盖'}
                              </p>
                            </div>
                          ))}
                        </div>
                      </details>

                      <div className="rounded-2xl border border-white/8 bg-surface-high p-5">
                        <div className="mb-4 flex items-center gap-2">
                          <Clock3 className="h-4 w-4 text-primary" />
                          <h4 className="text-sm font-bold uppercase tracking-[0.16em] text-primary">
                            事件日志
                          </h4>
                        </div>
                        <div className="space-y-3">
                          {workspace.events.length === 0 ? (
                            <p className="text-sm text-text-soft">暂无事件</p>
                          ) : (
                            workspace.events
                              .slice()
                              .reverse()
                              .slice(0, 6)
                              .map((event, index) => (
                                <div
                                  key={`${String(event.timestamp)}-${index}`}
                                  className="rounded-xl border border-white/6 bg-surface p-4"
                                >
                                  <p className="text-sm font-semibold text-white">
                                    {String(event.action ?? '未知动作')}
                                  </p>
                                  <p className="mt-1 text-xs text-text-soft">
                                    {formatRelativeDate(String(event.timestamp ?? ''))}
                                  </p>
                                </div>
                              ))
                          )}
                        </div>
                      </div>

                      <div className="rounded-2xl border border-white/8 bg-surface-high p-5">
                        <div className="mb-4 flex items-center gap-2">
                          <MessageSquareText className="h-4 w-4 text-primary" />
                          <h4 className="text-sm font-bold uppercase tracking-[0.16em] text-primary">
                            聊天控制
                          </h4>
                        </div>
                        <p className="text-sm leading-6 text-text-soft">
                          聊天面板后面会继续增强，但这里已经预留了真实上下文位置。
                        </p>
                        {workspace.chat.length > 0 ? (
                          <p className="mt-3 text-xs text-text-soft">
                            当前已记录 {workspace.chat.length} 条聊天消息。
                          </p>
                        ) : null}
                      </div>
                    </aside>

                    <div className="space-y-5">
                      <div className="flex items-center justify-between gap-4">
                        <div className="inline-flex rounded-md bg-surface-high p-1">
                          {(
                            [
                              ['overview', '总览'],
                              ['brief', '设计说明'],
                              ['prompt', '出图指令'],
                              ['candidate', '候选池'],
                            ] as const
                          ).map(([value, label]) => (
                            <button
                              key={value}
                              className={clsx(
                                'rounded-md px-4 py-2 text-sm font-medium transition',
                                outputTab === value
                                  ? 'bg-primary text-black'
                                  : 'text-text-soft hover:text-white',
                              )}
                              onClick={() => setOutputTab(value)}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                        <div className="text-sm text-text-soft">
                          当前版本：
                          {workspace.current_image_version ||
                            workspace.prompt?.version ||
                            workspace.brief?.version ||
                            '暂无'}
                        </div>
                      </div>

                      {outputTab === 'overview' ? (
                        <div className="grid gap-5 lg:grid-cols-2">
                          <div className="rounded-2xl border border-white/8 bg-surface-high p-5">
                            <h4 className="mb-3 text-lg font-semibold text-white">
                              当前设计说明
                            </h4>
                            <div className="space-y-3 text-sm">
                              <div>
                                <p className="mb-1 text-text-soft">名称</p>
                                <p className="font-semibold text-white">
                                  {String(briefOutput.title ?? activeItem.title)}
                                </p>
                              </div>
                              <div>
                                <p className="mb-1 text-text-soft">需求整理</p>
                                <p className="leading-7 text-white/90">
                                  {String(briefOutput.description ?? '暂无设计说明')}
                                </p>
                              </div>
                              <div>
                                <p className="mb-1 text-text-soft">关键词</p>
                                <p className="leading-7 text-white/90">
                                  {stringList(briefOutput.keywords).join(' · ') || '暂无'}
                                </p>
                              </div>
                            </div>
                          </div>
                          <div className="rounded-2xl border border-white/8 bg-surface-high p-5">
                            <h4 className="mb-3 text-lg font-semibold text-white">
                              当前候选图
                            </h4>
                            {workspace.candidate_pool.approved_image_url ? (
                              <img
                                src={workspace.candidate_pool.approved_image_url}
                                alt="approved"
                                className="aspect-square w-full rounded-2xl object-cover"
                              />
                            ) : selectedCandidateVersion?.candidates[0]?.image_url ? (
                              <img
                                src={selectedCandidateVersion.candidates[0].image_url!}
                                alt={selectedCandidateVersion.version}
                                className="aspect-square w-full rounded-2xl object-cover"
                              />
                            ) : (
                              <div className="flex aspect-square items-center justify-center rounded-2xl border border-dashed border-primary/25 bg-primary/6">
                                <div className="text-center">
                                  <ImageIcon className="mx-auto mb-3 h-8 w-8 text-primary" />
                                  <p className="text-sm font-medium text-white">还没有候选图</p>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>
                      ) : null}

                      {outputTab === 'brief' ? (
                        <div className="rounded-2xl border border-white/8 bg-surface-high p-6">
                          <div className="mb-4 flex items-center justify-between">
                            <div>
                              <h4 className="text-lg font-semibold text-white">设计说明</h4>
                              <p className="mt-1 text-sm text-text-soft">
                                {workspace.brief
                                  ? `${workspace.brief.version} · ${modelLabel(workspace.brief.model)}`
                                  : '当前还没有设计说明'}
                              </p>
                            </div>
                            {workspace.brief ? <Pill status="brief_generated" /> : null}
                          </div>
                          <div className="grid gap-4 md:grid-cols-2">
                            <div className="rounded-2xl border border-white/8 bg-surface p-4">
                              <p className="mb-2 text-text-soft">名称</p>
                              <p className="font-semibold text-white">
                                {String(briefOutput.title ?? activeItem.title)}
                              </p>
                            </div>
                            <div className="rounded-2xl border border-white/8 bg-surface p-4">
                              <p className="mb-2 text-text-soft">视觉重点</p>
                              <p className="font-semibold text-white">
                                {String(briefOutput.visual_focus ?? '暂无')}
                              </p>
                            </div>
                          </div>
                          <div className="mt-4 rounded-2xl border border-white/8 bg-surface p-4">
                            <p className="mb-2 text-text-soft">需求整理</p>
                            <p className="text-sm leading-7 text-white/90">
                              {String(briefOutput.description ?? '暂无设计说明')}
                            </p>
                          </div>
                          <div className="mt-4 rounded-2xl border border-white/8 bg-surface p-4">
                            <p className="mb-2 text-text-soft">关键词</p>
                            <p className="text-sm leading-7 text-white/90">
                              {stringList(briefOutput.keywords).join(' · ') || '暂无'}
                            </p>
                          </div>
                        </div>
                      ) : null}

                      {outputTab === 'prompt' ? (
                        <div className="rounded-2xl border border-white/8 bg-surface-high p-6">
                          <div className="mb-4 flex items-center justify-between">
                            <div>
                              <h4 className="text-lg font-semibold text-white">出图指令</h4>
                              <p className="mt-1 text-sm text-text-soft">
                                {workspace.prompt
                                  ? `${workspace.prompt.version} · ${modelLabel(workspace.prompt.model)}`
                                  : '当前还没有出图指令'}
                              </p>
                            </div>
                            {workspace.prompt ? <Pill status="prompt_generated" /> : null}
                          </div>

                          <div className="space-y-4">
                            <div className="rounded-2xl border border-white/8 bg-surface p-4">
                              <p className="mb-2 flex items-center gap-2 text-text-soft">
                                <FileText className="h-4 w-4" />
                                Prompt
                              </p>
                              <p className="text-sm leading-7 text-white/90">
                                {String(promptOutput.prompt ?? '暂无出图指令')}
                              </p>
                            </div>
                            <div className="rounded-2xl border border-white/8 bg-surface p-4">
                              <p className="mb-2 text-text-soft">Negative Prompt</p>
                              <p className="text-sm leading-7 text-white/90">
                                {String(promptOutput.negative_prompt ?? '暂无')}
                              </p>
                            </div>
                            <div className="grid gap-4 md:grid-cols-2">
                              <div className="rounded-2xl border border-white/8 bg-surface p-4">
                                <p className="mb-2 text-text-soft">来源设计说明</p>
                                <p className="font-semibold text-white">
                                  {String(inputRecord(workspace.prompt).brief_version ?? '暂无')}
                                </p>
                              </div>
                              <div className="rounded-2xl border border-white/8 bg-surface p-4">
                                <p className="mb-2 text-text-soft">当前模型</p>
                                <p className="font-semibold text-white">
                                  {modelLabel(workspace.prompt?.model)}
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      ) : null}

                      {outputTab === 'candidate' ? (
                        <div className="space-y-5">
                          <div className="rounded-2xl border border-white/8 bg-surface-high p-5">
                            <div className="mb-4 flex items-center justify-between">
                              <div>
                                <h4 className="text-lg font-semibold text-white">当前采用</h4>
                                <p className="mt-1 text-sm text-text-soft">
                                  已经按真实候选池展示当前采用图、历史图和生成中的任务。
                                </p>
                              </div>
                              <Pill status={activeItem.status} />
                            </div>

                            {workspace.candidate_pool.approved_image_url ? (
                              <img
                                src={workspace.candidate_pool.approved_image_url}
                                alt="approved"
                                className="aspect-[16/10] w-full rounded-2xl object-cover"
                              />
                            ) : (
                              <div className="flex aspect-[16/10] items-center justify-center rounded-2xl border border-dashed border-primary/25 bg-primary/6 text-text-soft">
                                尚未确认最终候选图
                              </div>
                            )}
                          </div>

                          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                            {candidateVersions.length === 0 ? (
                              <div className="col-span-full rounded-2xl border border-dashed border-white/10 bg-surface-high p-6 text-sm text-text-soft">
                                当前还没有候选池内容。
                              </div>
                            ) : (
                              candidateVersions.map((version) => (
                                <CandidateVersionCard
                                  key={version.version}
                                  version={version}
                                />
                              ))
                            )}
                          </div>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </section>
              ) : null}
            </>
          )}
        </div>
      </main>

      <ProvidersModal
        open={settingsOpen}
        providers={providers}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  )
}

export default App
