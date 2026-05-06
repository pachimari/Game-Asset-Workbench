import AppShell from './components/AppShell'
import { useWorkbenchController } from './hooks/useWorkbenchController'

function App() {
  const controller = useWorkbenchController()
  return (
    <AppShell
      dashboardScrollRef={controller.dashboardScrollRef}
      tasks={controller.tasks}
      activeTaskId={controller.activeTaskId}
      activeTask={controller.activeTask}
      items={controller.items}
      sheets={controller.sheets}
      activeItemId={controller.activeItemId}
      activeItem={controller.activeItem}
      workspace={controller.workspace}
      view={controller.view}
      globalSettings={controller.globalSettings}
      settingsOpen={controller.settingsOpen}
      loading={controller.loading}
      error={controller.error}
      actionError={controller.actionError}
      actionBusy={controller.actionBusy}
      settingsBusy={controller.settingsBusy}
      pendingRunStep={controller.pendingRunStep}
      setSettingsOpen={controller.setSettingsOpen}
      onSelectTask={controller.handleSelectTask}
      onSelectItem={controller.handleSelectItem}
      onBackToDashboard={controller.handleBackToDashboard}
      onCreateTask={controller.handleCreateTask}
      onCreateItem={controller.handleCreateItem}
      onCreateItemsBulk={controller.handleCreateItemsBulk}
      onUpdateItemInput={controller.handleUpdateItemInput}
      onDeleteTask={controller.handleDeleteTask}
      onSaveTaskSettings={controller.handleUpdateTaskSettings}
      onRunBatchPipeline={controller.handleRunBatchPipeline}
      onExportStarredImages={controller.handleExportStarredImages}
      onGridSheetAction={controller.handleGridSheetAction}
      onEditBrief={controller.handleEditBrief}
      onEditPrompt={controller.handleEditPrompt}
      onUpdateItemModel={controller.handleUpdateItemModel}
      onSelectVersion={controller.handleSelectCurrentVersion}
      onToggleCandidateStar={controller.handleToggleCandidateStar}
      onRunStep={(step) => controller.handleWorkspaceAction('run', step)}
      onApproveStep={(step) => controller.handleWorkspaceAction('approve', step)}
      onRollbackStep={(step) => controller.handleWorkspaceAction('rollback', step)}
      onCancelImage={() => controller.handleWorkspaceAction('cancel')}
      onSaveTemplates={controller.handleSaveTemplates}
      onSaveDefaults={controller.handleSaveDefaults}
      onCreateProvider={controller.handleCreateProvider}
      onUpdateProvider={controller.handleUpdateProvider}
      onDeleteProvider={controller.handleDeleteProvider}
      onSyncProvider={controller.handleSyncProvider}
    />
  )
}

export default App
