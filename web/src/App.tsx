import { useEffect, useEffectEvent, useRef, useState } from 'react'
import {
  approveItemStep,
  cancelItemImage,
  deleteTask,
  createTaskItem,
  createTask,
  createProvider,
  deleteProvider,
  fetchSettings,
  fetchTask,
  fetchTaskItem,
  fetchTaskItems,
  fetchTaskItemWorkspace,
  fetchTasks,
  pollItemImage,
  rollbackItemStep,
  runItemStep,
  saveGlobalDefaults,
  savePromptTemplates,
  syncProviderModels,
  updateTask,
  updateProvider,
} from './lib/api'
import type {
  GlobalSettingsData,
  ItemSummary,
  TaskSummary,
  WorkspacePayload,
} from './types'

import Sidebar from './components/Sidebar'
import TopBar from './components/TopBar'
import BatchDashboard from './components/BatchDashboard'
import ItemWorkspace from './components/ItemWorkspace'
import GlobalSettings from './components/GlobalSettings'

type View = 'dashboard' | 'workspace'

function App() {
  const dashboardScrollRef = useRef<HTMLDivElement | null>(null)
  const dashboardScrollTopRef = useRef(0)
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null)
  const [items, setItems] = useState<ItemSummary[]>([])
  const [activeItemId, setActiveItemId] = useState<string | null>(null)
  const [activeItem, setActiveItem] = useState<ItemSummary | null>(null)
  const [workspace, setWorkspace] = useState<WorkspacePayload | null>(null)
  const [view, setView] = useState<View>('dashboard')
  const [globalSettings, setGlobalSettings] = useState<GlobalSettingsData | null>(null)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [actionBusy, setActionBusy] = useState(false)
  const [settingsBusy, setSettingsBusy] = useState(false)

  async function reloadTaskList(preferredTaskId?: string) {
    const rows = await fetchTasks()
    setTasks(rows)
    setActiveTaskId((cur) => preferredTaskId ?? cur ?? rows[0]?.task_id ?? null)
    return rows
  }

  async function reloadTaskContext(taskId: string, preferredItemId?: string | null) {
    const [task, itemRows] = await Promise.all([fetchTask(taskId), fetchTaskItems(taskId)])
    setActiveTask(task)
    setItems(itemRows)
    const nextItemId =
      preferredItemId && itemRows.some((row) => row.item_id === preferredItemId)
        ? preferredItemId
        : itemRows[0]?.item_id ?? null
    setActiveItemId(nextItemId)
    return { task, itemRows, nextItemId }
  }

  async function reloadWorkspace(taskId: string, itemId: string) {
    const [item, ws] = await Promise.all([
      fetchTaskItem(taskId, itemId),
      fetchTaskItemWorkspace(taskId, itemId),
    ])
    setActiveItem(item)
    setWorkspace(ws)
    return { item, ws }
  }

  async function afterMutation(options?: { taskId?: string; itemId?: string | null }) {
    const taskId = options?.taskId ?? activeTaskId
    if (!taskId) return
    const { nextItemId } = await reloadTaskContext(taskId, options?.itemId ?? activeItemId)
    if (nextItemId) {
      await reloadWorkspace(taskId, nextItemId)
    } else {
      setActiveItem(null)
      setWorkspace(null)
    }
    await reloadTaskList(taskId)
  }

  useEffect(() => {
    async function bootstrap() {
      setLoading(true)
      setError(null)
      try {
        const [taskRows, settingsData] = await Promise.all([fetchTasks(), fetchSettings()])
        setTasks(taskRows)
        setGlobalSettings(settingsData)
        if (taskRows.length > 0) {
          setActiveTaskId((cur) => cur ?? taskRows[0].task_id)
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
    async function load() {
      try {
        await reloadTaskContext(taskId)
      } catch (err) {
        setError(err instanceof Error ? err.message : '读取批次失败')
      }
    }
    void load()
  }, [activeTaskId])

  useEffect(() => {
    if (!activeTaskId || !activeItemId) {
      setActiveItem(null)
      setWorkspace(null)
      return
    }
    const taskId = activeTaskId
    const itemId = activeItemId
    async function load() {
      try {
        await reloadWorkspace(taskId, itemId)
      } catch (err) {
        setError(err instanceof Error ? err.message : '读取条目失败')
      }
    }
    void load()
  }, [activeTaskId, activeItemId])

  function handleSelectTask(taskId: string) {
    dashboardScrollTopRef.current = 0
    setActiveTaskId(taskId)
    setActiveItemId(null)
    setActiveItem(null)
    setWorkspace(null)
    setView('dashboard')
  }

  function handleSelectItem(itemId: string) {
    dashboardScrollTopRef.current = dashboardScrollRef.current?.scrollTop ?? 0
    setActiveItemId(itemId)
    setView('workspace')
  }

  function handleBackToDashboard() {
    setView('dashboard')
  }

  async function handleCreateTask(payload: {
    task_name: string
    project_background: string
    style_requirements: string
    asset_domain: string
  }) {
    setActionError(null)
    setActionBusy(true)
    try {
      const created = await createTask(payload)
      await reloadTaskList(created.task_id)
      await reloadTaskContext(created.task_id, null)
      setView('dashboard')
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '创建批次失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleCreateItem(payload: {
    asset_type: string
    title: string
    description: string
    category: string
    extra_context: string
  }) {
    if (!activeTaskId) return
    setActionError(null)
    setActionBusy(true)
    try {
      const created = await createTaskItem(activeTaskId, payload)
      await afterMutation({ taskId: activeTaskId, itemId: created.item_id })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '创建条目失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleCreateItemsBulk(
    payloads: Array<{
      asset_type: string
      title: string
      description: string
      category: string
      extra_context: string
      image_aspect_ratio?: string | null
      image_resolution?: string | null
    }>,
  ) {
    if (!activeTaskId || payloads.length === 0) return
    setActionError(null)
    setActionBusy(true)
    try {
      for (const payload of payloads) {
        await createTaskItem(activeTaskId, payload)
      }
      await afterMutation({ taskId: activeTaskId })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '批量导入失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleDeleteTask(taskId: string) {
    const targetTask = tasks.find((task) => task.task_id === taskId)
    const confirmed = window.confirm(`确认删除批次「${targetTask?.task_name ?? taskId}」？此操作不可撤销。`)
    if (!confirmed) return

    setActionError(null)
    setActionBusy(true)
    try {
      await deleteTask(taskId)
      const rows = await fetchTasks()
      setTasks(rows)
      const nextTaskId = rows[0]?.task_id ?? null
      setActiveTaskId(nextTaskId)
      setActiveItemId(null)
      setActiveItem(null)
      setWorkspace(null)
      setView('dashboard')
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '删除批次失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleUpdateTaskSettings(payload: {
    task_name: string
    project_background: string
    style_requirements: string
    asset_domain: string
    image_aspect_ratio: string
    image_resolution: string
  }) {
    if (!activeTaskId) return
    setActionError(null)
    setActionBusy(true)
    try {
      const updated = await updateTask(activeTaskId, payload)
      setActiveTask(updated)
      await reloadTaskList(activeTaskId)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '保存批次设定失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleWorkspaceAction(
    action: 'run' | 'approve' | 'rollback' | 'poll' | 'cancel',
    step?: string,
    version?: string,
  ) {
    if (!activeTaskId || !activeItemId) return
    setActionError(null)
    setActionBusy(true)
    try {
      if (action === 'run' && step) {
        await runItemStep(activeTaskId, activeItemId, step)
      } else if (action === 'approve' && step) {
        await approveItemStep(activeTaskId, activeItemId, step)
      } else if (action === 'rollback' && step) {
        await rollbackItemStep(activeTaskId, activeItemId, step)
      } else if (action === 'poll') {
        await pollItemImage(activeTaskId, activeItemId, version)
      } else if (action === 'cancel') {
        await cancelItemImage(activeTaskId, activeItemId)
      }
      await afterMutation({ taskId: activeTaskId, itemId: activeItemId })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '执行动作失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleSaveTemplates(payload: {
    brief_system_prompt?: string | null
    prompt_system_prompt?: string | null
  }) {
    setSettingsBusy(true)
    try {
      const next = await savePromptTemplates(payload)
      setGlobalSettings(next)
    } finally {
      setSettingsBusy(false)
    }
  }

  async function handleSaveDefaults(payload: {
    brief_provider?: string | null
    brief_model?: string | null
    prompt_provider?: string | null
    prompt_model?: string | null
    image_provider?: string | null
    image_model?: string | null
  }) {
    setSettingsBusy(true)
    try {
      const next = await saveGlobalDefaults(payload)
      setGlobalSettings(next)
    } finally {
      setSettingsBusy(false)
    }
  }

  async function handleCreateProvider(payload: {
    label: string
    provider_type: string
    base_url: string
    api_key: string
  }) {
    setSettingsBusy(true)
    try {
      const next = await createProvider(payload)
      setGlobalSettings(next)
    } finally {
      setSettingsBusy(false)
    }
  }

  async function handleUpdateProvider(
    providerId: string,
    payload: {
      label: string
      provider_type: string
      base_url: string
      api_key: string
    },
  ) {
    setSettingsBusy(true)
    try {
      const next = await updateProvider(providerId, payload)
      setGlobalSettings(next)
    } finally {
      setSettingsBusy(false)
    }
  }

  async function handleDeleteProvider(providerId: string) {
    setSettingsBusy(true)
    try {
      const next = await deleteProvider(providerId)
      setGlobalSettings(next)
    } finally {
      setSettingsBusy(false)
    }
  }

  async function handleSyncProvider(providerId: string) {
    setSettingsBusy(true)
    try {
      const next = await syncProviderModels(providerId)
      setGlobalSettings(next)
    } finally {
      setSettingsBusy(false)
    }
  }

  const pollCurrentWorkspace = useEffectEvent(() => {
    void handleWorkspaceAction('poll')
  })

  useEffect(() => {
    if (!activeTaskId || !activeItemId || workspace?.status !== 'image_generating') return
    const timer = window.setInterval(() => {
      pollCurrentWorkspace()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [activeTaskId, activeItemId, workspace?.status])

  useEffect(() => {
    if (view !== 'dashboard') return
    const container = dashboardScrollRef.current
    if (!container) return
    const frame = window.requestAnimationFrame(() => {
      container.scrollTop = dashboardScrollTopRef.current
    })
    return () => window.cancelAnimationFrame(frame)
  }, [view, activeTaskId])

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-sm text-on-surface-variant">正在加载工作台...</p>
        </div>
      </div>
    )
  }

  if (error && !activeTask) {
    return (
      <div className="flex h-screen items-center justify-center bg-surface">
        <div className="max-w-md text-center">
          <p className="mb-2 text-lg font-bold text-on-surface">读取失败</p>
          <p className="text-sm text-on-surface-variant">
            无法连接本地 API：{error}。请先启动后端服务，再刷新页面。
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen overflow-hidden bg-background text-on-surface">
      <Sidebar
        tasks={tasks}
        activeTaskId={activeTaskId}
        onSelectTask={handleSelectTask}
        onOpenSettings={() => setSettingsOpen(true)}
        onCreateTask={handleCreateTask}
        onDeleteTask={handleDeleteTask}
        productName=""
      />

      <main className="ml-52 flex h-screen min-h-0 flex-col overflow-hidden">
        <TopBar
          title="工作台"
          breadcrumb={
            view === 'workspace' && activeItem
              ? `${activeTask?.task_name ?? ''} > ${activeItem.title}`
              : activeTask?.task_name
          }
        />

        <div className="min-h-0 flex-1 overflow-hidden">
          {view === 'workspace' && activeItem && workspace ? (
            <ItemWorkspace
              item={activeItem}
              workspace={workspace}
              actionBusy={actionBusy}
              actionError={actionError}
              taskName={activeTask?.task_name ?? ''}
              onBackToDashboard={handleBackToDashboard}
              onRunStep={(step) => handleWorkspaceAction('run', step)}
              onApproveStep={(step) => handleWorkspaceAction('approve', step)}
              onRollbackStep={(step) => handleWorkspaceAction('rollback', step)}
              onPollImage={(version) => handleWorkspaceAction('poll', undefined, version)}
              onCancelImage={() => handleWorkspaceAction('cancel')}
            />
          ) : activeTask ? (
            <div ref={dashboardScrollRef} className="h-full overflow-y-auto">
              <BatchDashboard
                task={activeTask}
                items={items}
                activeItemId={activeItemId}
                onSelectItem={handleSelectItem}
                onSaveTaskSettings={handleUpdateTaskSettings}
                onCreateItem={handleCreateItem}
                onCreateItemsBulk={handleCreateItemsBulk}
                actionBusy={actionBusy}
                actionError={actionError}
              />
            </div>
          ) : (
            <div className="flex h-full items-center justify-center p-8">
              <div className="text-center">
                <span className="material-symbols-outlined mb-4 text-4xl text-outline">inbox</span>
                <h3 className="mb-2 text-2xl font-bold text-on-surface">还没有批次</h3>
                <p className="text-sm text-on-surface-variant">创建一个批次后开始工作</p>
              </div>
            </div>
          )}
        </div>
      </main>

      <GlobalSettings
        open={settingsOpen}
        settings={globalSettings}
        saving={settingsBusy}
        onClose={() => setSettingsOpen(false)}
        onSaveTemplates={handleSaveTemplates}
        onSaveDefaults={handleSaveDefaults}
        onCreateProvider={handleCreateProvider}
        onUpdateProvider={handleUpdateProvider}
        onDeleteProvider={handleDeleteProvider}
        onSyncProvider={handleSyncProvider}
      />
    </div>
  )
}

export default App
