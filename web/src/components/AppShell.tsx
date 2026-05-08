import type { RefObject } from 'react'

import BatchDashboard from './BatchDashboard'
import GlobalSettings from './GlobalSettings'
import ItemWorkspace from './ItemWorkspace'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import type {
  GlobalSettingsData,
  GridSheetSummary,
  ItemSummary,
  TaskSummary,
  WorkspacePayload,
} from '../types'
import type { View } from '../hooks/useWorkbenchController'

type Props = {
  dashboardScrollRef: RefObject<HTMLDivElement | null>
  tasks: TaskSummary[]
  activeTaskId: string | null
  activeTask: TaskSummary | null
  items: ItemSummary[]
  sheets: GridSheetSummary[]
  activeItemId: string | null
  activeItem: ItemSummary | null
  workspace: WorkspacePayload | null
  view: View
  globalSettings: GlobalSettingsData | null
  settingsOpen: boolean
  loading: boolean
  error: string | null
  actionError: string | null
  actionBusy: boolean
  settingsBusy: boolean
  pendingRunStep: 'brief_generation' | 'image_prompt' | 'image_generation' | null
  setSettingsOpen: (open: boolean) => void
  onSelectTask: (taskId: string) => void
  onSelectItem: (itemId: string) => void
  onBackToDashboard: () => Promise<void>
  onCreateTask: (payload: {
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
  }) => Promise<void>
  onCreateItem: (payload: {
    asset_type: string
    title: string
    description: string
    category: string
    extra_context: string
  }) => Promise<void>
  onCreateItemsBulk: (
    payloads: Array<{
      asset_type: string
      title: string
      description: string
      category: string
      extra_context: string
      image_aspect_ratio?: string | null
      image_resolution?: string | null
    }>,
  ) => Promise<void>
  onUpdateItemInput: (payload: {
    title?: string | null
    category?: string | null
    description?: string | null
    extra_context?: string | null
    image_aspect_ratio?: string | null
    image_resolution?: string | null
  }) => Promise<void>
  onDeleteTask: (taskId: string) => Promise<void>
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
      cropBoxPercent?: {
        left: number
        top: number
        right: number
        bottom: number
      }
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
  onUpdateItemModel: (
    stage: 'brief_generation' | 'image_prompt' | 'image_generation',
    token: string,
  ) => Promise<void>
  onSelectVersion: (
    step: 'brief_generation' | 'image_prompt' | 'image_generation',
    version: string,
  ) => Promise<void>
  onToggleCandidateStar: (version: string, starred: boolean) => Promise<void>
  onRunStep: (step: string) => Promise<void>
  onApproveStep: (step: string) => Promise<void>
  onRollbackStep: (step: string) => Promise<void>
  onCancelImage: () => Promise<void>
  onSaveTemplates: (payload: {
    brief_system_prompt?: string | null
    prompt_system_prompt?: string | null
    grid_sheet_prompt_template?: string | null
    grid_sheet_negative_prompt?: string | null
  }) => Promise<void>
  onSaveDefaults: (payload: {
    brief_provider?: string | null
    brief_model?: string | null
    prompt_provider?: string | null
    prompt_model?: string | null
    image_provider?: string | null
    image_model?: string | null
  }) => Promise<void>
  onCreateProvider: (payload: {
    label: string
    provider_type: string
    base_url: string
    api_key: string
  }) => Promise<string>
  onUpdateProvider: (
    providerId: string,
    payload: {
      label: string
      provider_type: string
      base_url: string
      api_key?: string
    },
  ) => Promise<string>
  onDeleteProvider: (providerId: string) => Promise<void>
  onSyncProvider: (providerId: string) => Promise<void>
}

export default function AppShell({
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
  onSelectTask,
  onSelectItem,
  onBackToDashboard,
  onCreateTask,
  onCreateItem,
  onCreateItemsBulk,
  onUpdateItemInput,
  onDeleteTask,
  onSaveTaskSettings,
  onRunBatchPipeline,
  onExportStarredImages,
  onGridSheetAction,
  onGridSheetTileAction,
  onEditBrief,
  onEditPrompt,
  onUpdateItemModel,
  onSelectVersion,
  onToggleCandidateStar,
  onRunStep,
  onApproveStep,
  onRollbackStep,
  onCancelImage,
  onSaveTemplates,
  onSaveDefaults,
  onCreateProvider,
  onUpdateProvider,
  onDeleteProvider,
  onSyncProvider,
}: Props) {
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
        onSelectTask={onSelectTask}
        onOpenSettings={() => setSettingsOpen(true)}
        onCreateTask={onCreateTask}
        onDeleteTask={onDeleteTask}
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
              task={activeTask}
              globalSettings={globalSettings}
              workspace={workspace}
              actionBusy={actionBusy}
              pendingRunStep={pendingRunStep}
              actionError={actionError}
              taskName={activeTask?.task_name ?? ''}
              onBackToDashboard={onBackToDashboard}
              onUpdateItemInput={onUpdateItemInput}
              onEditBrief={onEditBrief}
              onEditPrompt={onEditPrompt}
              onUpdateItemModel={onUpdateItemModel}
              onSelectVersion={onSelectVersion}
              onToggleCandidateStar={onToggleCandidateStar}
              onRunStep={onRunStep}
              onApproveStep={onApproveStep}
              onRollbackStep={onRollbackStep}
              onCancelImage={onCancelImage}
            />
          ) : activeTask ? (
            <div ref={dashboardScrollRef} className="h-full overflow-y-auto">
              <BatchDashboard
                task={activeTask}
                items={items}
                sheets={sheets}
                activeItemId={activeItemId}
                onSelectItem={onSelectItem}
                onSaveTaskSettings={onSaveTaskSettings}
                onRunBatchPipeline={onRunBatchPipeline}
                onExportStarredImages={onExportStarredImages}
                onGridSheetAction={onGridSheetAction}
                onGridSheetTileAction={onGridSheetTileAction}
                onCreateItem={onCreateItem}
                onCreateItemsBulk={onCreateItemsBulk}
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
        onSaveTemplates={onSaveTemplates}
        onSaveDefaults={onSaveDefaults}
        onCreateProvider={onCreateProvider}
        onUpdateProvider={onUpdateProvider}
        onDeleteProvider={onDeleteProvider}
        onSyncProvider={onSyncProvider}
      />
    </div>
  )
}
