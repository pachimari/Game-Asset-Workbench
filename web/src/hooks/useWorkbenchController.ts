import { useEffect, useEffectEvent, useRef, useState } from 'react'
import {
  approveItemStep,
  backfillTaskGridSheet,
  cancelItemImage,
  createItemFromGridSheetTile,
  createProvider,
  createTask,
  createTaskItem,
  deleteProvider,
  deleteTask,
  downloadTaskStarredImages,
  editTaskItemBrief,
  editTaskItemPrompt,
  fetchSettings,
  fetchTask,
  fetchTaskItem,
  fetchTaskItems,
  fetchTaskSheets,
  fetchTaskItemWorkspace,
  fetchTasks,
  generateTaskGridSheet,
  planTaskGridSheet,
  pollTaskGridSheet,
  pollItemImage,
  promoteTaskGridSheetTile,
  reviewTaskGridSheetTile,
  rollbackItemStep,
  runItemStep,
  runTaskPipeline,
  saveGlobalDefaults,
  savePromptTemplates,
  selectTaskItemVersion,
  splitTaskGridSheet,
  syncProviderModels,
  toggleTaskItemCandidateStar,
  updateProvider,
  updateTask,
  updateTaskItem,
} from '../lib/api'
import type {
  GlobalSettingsData,
  GridSheetSummary,
  ItemSummary,
  TaskSummary,
  WorkspacePayload,
} from '../types'

export type View = 'dashboard' | 'workspace'

function itemHasBackgroundWork(item: ItemSummary) {
  return (
    (item.pending_image_jobs ?? 0) > 0 ||
    item.status === 'brief_generating' ||
    item.status === 'prompt_generating' ||
    item.status === 'image_generating'
  )
}

function sheetHasBackgroundWork(sheet: GridSheetSummary) {
  return sheet.status === 'generating'
}

export function useWorkbenchController() {
  const dashboardScrollRef = useRef<HTMLDivElement | null>(null)
  const dashboardScrollTopRef = useRef(0)
  const workspacePollInFlightRef = useRef(false)
  const dashboardPollInFlightRef = useRef(false)
  const activeTaskIdRef = useRef<string | null>(null)
  const activeItemIdRef = useRef<string | null>(null)
  const [tasks, setTasks] = useState<TaskSummary[]>([])
  const [activeTaskId, setActiveTaskId] = useState<string | null>(null)
  const [activeTask, setActiveTask] = useState<TaskSummary | null>(null)
  const [items, setItems] = useState<ItemSummary[]>([])
  const [sheets, setSheets] = useState<GridSheetSummary[]>([])
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
  const [pendingRunStep, setPendingRunStep] = useState<
    'brief_generation' | 'image_prompt' | 'image_generation' | null
  >(null)

  useEffect(() => {
    activeTaskIdRef.current = activeTaskId
  }, [activeTaskId])

  useEffect(() => {
    activeItemIdRef.current = activeItemId
  }, [activeItemId])

  function clearWorkspaceActionState() {
    setActionBusy(false)
    setPendingRunStep(null)
    setActionError(null)
  }

  async function reloadTaskList(preferredTaskId?: string) {
    const rows = await fetchTasks()
    setTasks(rows)
    setActiveTaskId((cur) => preferredTaskId ?? cur ?? rows[0]?.task_id ?? null)
    return rows
  }

  async function reloadTaskContext(taskId: string, preferredItemId?: string | null) {
    const [task, itemRows, sheetRows] = await Promise.all([
      fetchTask(taskId),
      fetchTaskItems(taskId),
      fetchTaskSheets(taskId),
    ])
    setActiveTask(task)
    setItems(itemRows)
    setSheets(sheetRows)
    const nextItemId =
      preferredItemId && itemRows.some((row) => row.item_id === preferredItemId)
        ? preferredItemId
        : itemRows[0]?.item_id ?? null
    setActiveItemId(nextItemId)
    return { task, itemRows, sheetRows, nextItemId }
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
    if (view !== 'workspace') return
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
  }, [activeTaskId, activeItemId, view])

  function handleSelectTask(taskId: string) {
    dashboardScrollTopRef.current = 0
    clearWorkspaceActionState()
    setActiveTaskId(taskId)
      setActiveItemId(null)
      setActiveItem(null)
      setWorkspace(null)
      setSheets([])
      setView('dashboard')
  }

  function handleSelectItem(itemId: string) {
    dashboardScrollTopRef.current = dashboardScrollRef.current?.scrollTop ?? 0
    clearWorkspaceActionState()
    setActiveItemId(itemId)
    setView('workspace')
  }

  async function handleBackToDashboard() {
    clearWorkspaceActionState()
    try {
      if (activeTaskIdRef.current) {
        await reloadTaskContext(activeTaskIdRef.current, activeItemIdRef.current)
        await reloadTaskList(activeTaskIdRef.current)
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '刷新批次状态失败')
    } finally {
      setView('dashboard')
    }
  }

  async function handleCreateTask(payload: {
    task_name: string
    project_background: string
    style_requirements: string
    asset_domain: string
    image_generation_mode?: 'single' | 'grid_sheet'
    image_aspect_ratio?: string
    image_resolution?: string
    grid_rows?: number
    grid_cols?: number
    grid_padding?: number
    grid_gap?: number
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

  async function handleUpdateItemInput(payload: {
    title?: string | null
    category?: string | null
    description?: string | null
    extra_context?: string | null
    image_aspect_ratio?: string | null
    image_resolution?: string | null
  }) {
    if (!activeTaskId || !activeItemId) return
    setActionError(null)
    setActionBusy(true)
    try {
      await updateTaskItem(activeTaskId, activeItemId, payload)
      await afterMutation({ taskId: activeTaskId, itemId: activeItemId })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '保存原始输入失败')
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
      setSheets([])
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
    image_generation_mode: 'single' | 'grid_sheet'
    grid_rows: number
    grid_cols: number
    grid_padding: number
    grid_gap: number
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

  async function handleRunBatchPipeline(options?: { autoApprove?: boolean }) {
    if (!activeTaskId) return
    setActionError(null)
    setActionBusy(true)
    try {
      const response = await runTaskPipeline(activeTaskId, {
        auto_approve: options?.autoApprove ?? true,
      })
      setActiveTask(response.task)
      setItems(response.items)
      await reloadTaskList(activeTaskId)
      if (activeItemId && response.items.some((item) => item.item_id === activeItemId)) {
        await reloadWorkspace(activeTaskId, activeItemId)
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '批量执行失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleExportStarredImages() {
    if (!activeTaskId) return
    setActionError(null)
    setActionBusy(true)
    try {
      await downloadTaskStarredImages(activeTaskId)
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '导出星标图失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleGridSheetAction(
    action: 'plan' | 'generate' | 'poll' | 'split' | 'backfill',
    sheetId?: string,
  ) {
    if (!activeTaskId) return
    setActionError(null)
    setActionBusy(true)
    try {
      let response:
        | { sheet: GridSheetSummary; task?: TaskSummary; items?: ItemSummary[] }
        | undefined
      if (action === 'plan') {
        response = await planTaskGridSheet(activeTaskId)
      } else if (sheetId && action === 'generate') {
        response = await generateTaskGridSheet(activeTaskId, sheetId)
      } else if (sheetId && action === 'poll') {
        response = await pollTaskGridSheet(activeTaskId, sheetId)
      } else if (sheetId && action === 'split') {
        response = await splitTaskGridSheet(activeTaskId, sheetId)
      } else if (sheetId && action === 'backfill') {
        response = await backfillTaskGridSheet(activeTaskId, sheetId)
      }

      if (response?.task && response.items) {
        setActiveTask(response.task)
        setItems(response.items)
      }
      await reloadTaskContext(activeTaskId, activeItemId)
      await reloadTaskList(activeTaskId)
      if (activeItemId) {
        await reloadWorkspace(activeTaskId, activeItemId)
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '网格切图操作失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleGridSheetTileAction(
    action: 'pending' | 'rejected' | 'emergent' | 'promote' | 'create_item',
    sheetId: string,
    cellId: string,
    options?: {
      targetItemId?: string | null
      title?: string
      description?: string
    },
  ) {
    if (!activeTaskId) return
    setActionError(null)
    setActionBusy(true)
    try {
      let response:
        | { sheet: GridSheetSummary; task?: TaskSummary; items?: ItemSummary[] }
        | undefined
      if (action === 'promote') {
        response = await promoteTaskGridSheetTile(activeTaskId, sheetId, cellId, {
          target_item_id: options?.targetItemId ?? null,
          starred: true,
        })
      } else if (action === 'create_item') {
        response = await createItemFromGridSheetTile(activeTaskId, sheetId, cellId, {
          title: options?.title?.trim() || `${cellId} 涌现图标`,
          description: options?.description?.trim() || `从 ${sheetId} ${cellId} 采纳的涌现切片。`,
          asset_type: 'skill_icon',
          category: 'emergent',
          starred: true,
        })
      } else {
        response = await reviewTaskGridSheetTile(activeTaskId, sheetId, cellId, {
          review_status: action,
          target_item_id: options?.targetItemId ?? null,
        })
      }

      if (response?.task && response.items) {
        setActiveTask(response.task)
        setItems(response.items)
      }
      await reloadTaskContext(activeTaskId, activeItemId)
      await reloadTaskList(activeTaskId)
      if (activeItemId) {
        await reloadWorkspace(activeTaskId, activeItemId)
      }
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '更新切片审图状态失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleWorkspaceAction(
    action: 'run' | 'approve' | 'rollback' | 'poll' | 'cancel',
    step?: string,
    version?: string,
    options?: { passive?: boolean },
  ) {
    if (!activeTaskId || !activeItemId) return
    const requestTaskId = activeTaskId
    const requestItemId = activeItemId
    const passive = options?.passive ?? false
    if (!passive) {
      setActionError(null)
      setActionBusy(true)
      setPendingRunStep(action === 'run' && step ? (step as typeof pendingRunStep) : null)
      if (action === 'run' && step) {
        const optimisticStatus =
          step === 'brief_generation'
            ? 'brief_generating'
            : step === 'image_prompt'
              ? 'prompt_generating'
              : 'image_generating'

        setItems((current) =>
          current.map((row) =>
            row.item_id === requestItemId
              ? {
                  ...row,
                  status: optimisticStatus,
                  pending_image_jobs:
                    step === 'image_generation' ? (row.pending_image_jobs ?? 0) + 1 : row.pending_image_jobs,
                }
              : row,
          ),
        )
        setActiveItem((current) =>
          current && current.item_id === requestItemId ? { ...current, status: optimisticStatus } : current,
        )
        setWorkspace((current) =>
          current && current.item_id === requestItemId ? { ...current, status: optimisticStatus } : current,
        )
      }
    }
    try {
      let response:
        | { result: Record<string, unknown>; workspace: WorkspacePayload }
        | undefined

      if (action === 'run' && step) {
        response = await runItemStep(activeTaskId, activeItemId, step)
      } else if (action === 'approve' && step) {
        response = await approveItemStep(activeTaskId, activeItemId, step)
      } else if (action === 'rollback' && step) {
        response = await rollbackItemStep(activeTaskId, activeItemId, step)
      } else if (action === 'poll') {
        response = await pollItemImage(activeTaskId, activeItemId, version)
      } else if (action === 'cancel') {
        response = await cancelItemImage(activeTaskId, activeItemId)
      }

      const stillViewingSameItem =
        activeTaskIdRef.current === requestTaskId && activeItemIdRef.current === requestItemId

      if (response?.workspace && stillViewingSameItem) {
        setWorkspace(response.workspace)
        setActiveItem((current) =>
          current
            ? {
                ...current,
                status: response?.workspace.status ?? current.status,
                current_versions: response?.workspace.current_versions ?? current.current_versions,
              }
            : current,
        )
      }
      if (stillViewingSameItem) {
        await afterMutation({ taskId: requestTaskId, itemId: requestItemId })
      } else if (requestTaskId === activeTaskIdRef.current) {
        await reloadTaskContext(requestTaskId, activeItemIdRef.current)
        await reloadTaskList(requestTaskId)
      }
    } catch (err) {
      if (!passive) {
        setActionError(err instanceof Error ? err.message : '执行动作失败')
        if (requestTaskId === activeTaskIdRef.current) {
          await reloadTaskContext(requestTaskId, activeItemIdRef.current)
          if (view === 'workspace' && activeItemIdRef.current) {
            await reloadWorkspace(requestTaskId, activeItemIdRef.current)
          }
        }
      }
    } finally {
      if (!passive) {
        setActionBusy(false)
        setPendingRunStep(null)
      }
    }
  }

  async function handleEditBrief(payload: {
    title?: string | null
    description?: string | null
    visual_focus?: string | null
    keywords?: string[] | null
    note?: string | null
  }) {
    if (!activeTaskId || !activeItemId) return
    setActionError(null)
    setActionBusy(true)
    try {
      await editTaskItemBrief(activeTaskId, activeItemId, payload)
      await afterMutation({ taskId: activeTaskId, itemId: activeItemId })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '保存设计说明失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleEditPrompt(payload: {
    prompt?: string | null
    negative_prompt?: string | null
    note?: string | null
  }) {
    if (!activeTaskId || !activeItemId) return
    setActionError(null)
    setActionBusy(true)
    try {
      await editTaskItemPrompt(activeTaskId, activeItemId, payload)
      await afterMutation({ taskId: activeTaskId, itemId: activeItemId })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '保存出图指令失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleUpdateItemModel(stage: 'brief_generation' | 'image_prompt' | 'image_generation', token: string) {
    if (!activeTaskId || !activeItemId) return
    const payload =
      stage === 'brief_generation'
        ? token === '__inherit__'
          ? { brief_provider: null, brief_model: null }
          : {
              brief_provider: token.split('::')[0] ?? null,
              brief_model: token.split('::')[1] ?? null,
            }
        : stage === 'image_prompt'
          ? token === '__inherit__'
            ? { prompt_provider: null, prompt_model: null }
            : {
                prompt_provider: token.split('::')[0] ?? null,
                prompt_model: token.split('::')[1] ?? null,
              }
          : token === '__inherit__'
            ? { image_provider: null, image_model: null }
            : {
                image_provider: token.split('::')[0] ?? null,
                image_model: token.split('::')[1] ?? null,
              }

    setActionError(null)
    setActionBusy(true)
    try {
      await updateTaskItem(activeTaskId, activeItemId, payload)
      await afterMutation({ taskId: activeTaskId, itemId: activeItemId })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '更新模型失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleSelectCurrentVersion(step: 'brief_generation' | 'image_prompt' | 'image_generation', version: string) {
    if (!activeTaskId || !activeItemId) return
    setActionError(null)
    setActionBusy(true)
    try {
      await selectTaskItemVersion(activeTaskId, activeItemId, step, version)
      await afterMutation({ taskId: activeTaskId, itemId: activeItemId })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '切换当前版本失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleToggleCandidateStar(version: string, starred: boolean) {
    if (!activeTaskId || !activeItemId) return
    setActionError(null)
    setActionBusy(true)
    try {
      await toggleTaskItemCandidateStar(activeTaskId, activeItemId, version, starred)
      await afterMutation({ taskId: activeTaskId, itemId: activeItemId })
    } catch (err) {
      setActionError(err instanceof Error ? err.message : '更新星标失败')
    } finally {
      setActionBusy(false)
    }
  }

  async function handleSaveTemplates(payload: {
    brief_system_prompt?: string | null
    prompt_system_prompt?: string | null
    grid_sheet_prompt_template?: string | null
    grid_sheet_negative_prompt?: string | null
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
      const previousIds = new Set(globalSettings?.providers.map((provider) => provider.id) ?? [])
      const next = await createProvider(payload)
      setGlobalSettings(next)
      const created =
        next.providers.find((provider) => !previousIds.has(provider.id)) ??
        next.providers.find(
          (provider) =>
            !provider.builtin &&
            provider.label === payload.label &&
            provider.provider_type === payload.provider_type &&
            provider.base_url === payload.base_url,
        )
      return created?.id ?? ''
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
      api_key?: string
    },
  ) {
    setSettingsBusy(true)
    try {
      const next = await updateProvider(providerId, payload)
      setGlobalSettings(next)
      return providerId
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
    if (workspacePollInFlightRef.current) return
    workspacePollInFlightRef.current = true
    void handleWorkspaceAction('poll', undefined, undefined, { passive: true }).finally(() => {
      workspacePollInFlightRef.current = false
    })
  })

  useEffect(() => {
    const pendingCount =
      workspace?.candidate_pool.versions.filter((version) =>
        ['queued', 'submitted', 'processing', 'pending', 'running', 'in_progress'].includes(
          String(version.async_job?.status ?? '').toLowerCase(),
        ),
      ).length ?? 0
    if (!activeTaskId || !activeItemId || pendingCount === 0) return
    const timer = window.setInterval(() => {
      pollCurrentWorkspace()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [activeTaskId, activeItemId, workspace?.candidate_pool.versions])

  const pollDashboardTask = useEffectEvent(() => {
    if (!activeTaskId || dashboardPollInFlightRef.current) return
    const taskId = activeTaskId
    const generatingSheets = sheets.filter(sheetHasBackgroundWork)
    dashboardPollInFlightRef.current = true
    void Promise.allSettled(
      generatingSheets.map((sheet) => pollTaskGridSheet(taskId, sheet.sheet_id)),
    )
      .then(() => reloadTaskContext(taskId, activeItemIdRef.current))
      .then(() => reloadTaskList(taskId))
      .finally(() => {
        dashboardPollInFlightRef.current = false
      })
  })

  useEffect(() => {
    const hasBackgroundWork = items.some(itemHasBackgroundWork) || sheets.some(sheetHasBackgroundWork)
    if (!activeTaskId || !hasBackgroundWork) return
    const timer = window.setInterval(() => {
      pollDashboardTask()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [activeTaskId, items, sheets])

  useEffect(() => {
    if (
      view !== 'dashboard' ||
      !activeTaskId ||
      (!items.some(itemHasBackgroundWork) && !sheets.some(sheetHasBackgroundWork))
    ) {
      return
    }
    pollDashboardTask()
  }, [view, activeTaskId, items, sheets])

  useEffect(() => {
    if (view !== 'dashboard') return
    const container = dashboardScrollRef.current
    if (!container) return
    const frame = window.requestAnimationFrame(() => {
      container.scrollTop = dashboardScrollTopRef.current
    })
    return () => window.cancelAnimationFrame(frame)
  }, [view, activeTaskId])

  return {
    dashboardScrollRef,
    tasks,
    activeTaskId,
    activeTask,
    items,
    sheets,
    activeItemId,
    activeItem,
    workspace,
    view,
    globalSettings,
    settingsOpen,
    loading,
    error,
    actionError,
    actionBusy,
    settingsBusy,
    pendingRunStep,
    setSettingsOpen,
    handleSelectTask,
    handleSelectItem,
    handleBackToDashboard,
    handleCreateTask,
    handleCreateItem,
    handleCreateItemsBulk,
    handleUpdateItemInput,
    handleDeleteTask,
    handleUpdateTaskSettings,
    handleRunBatchPipeline,
    handleExportStarredImages,
    handleGridSheetAction,
    handleGridSheetTileAction,
    handleEditBrief,
    handleEditPrompt,
    handleUpdateItemModel,
    handleSelectCurrentVersion,
    handleToggleCandidateStar,
    handleSaveTemplates,
    handleSaveDefaults,
    handleCreateProvider,
    handleUpdateProvider,
    handleDeleteProvider,
    handleSyncProvider,
    handleWorkspaceAction,
  }
}
