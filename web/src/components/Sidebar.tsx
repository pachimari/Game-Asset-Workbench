import clsx from 'clsx'
import { useState } from 'react'
import type { TaskSummary } from '../types'

function Icon({ name, className, filled }: { name: string; className?: string; filled?: boolean }) {
  return (
    <span
      className={clsx('material-symbols-outlined', className)}
      style={filled ? { fontVariationSettings: "'FILL' 1" } : undefined}
    >
      {name}
    </span>
  )
}

export default function Sidebar({
  tasks,
  activeTaskId,
  onSelectTask,
  onOpenSettings,
  onCreateTask,
  onDeleteTask,
  productName,
}: {
  tasks: TaskSummary[]
  activeTaskId: string | null
  onSelectTask: (taskId: string) => void
  onOpenSettings: () => void
  onCreateTask: (payload: {
    task_name: string
    project_background: string
    style_requirements: string
    asset_domain: string
  }) => Promise<void>
  onDeleteTask: (taskId: string) => Promise<void>
  productName?: string
}) {
  const [creating, setCreating] = useState(false)
  const [taskName, setTaskName] = useState('')
  const [projectBackground, setProjectBackground] = useState('')
  const [styleRequirements, setStyleRequirements] = useState('')
  const [assetDomain, setAssetDomain] = useState('game_icon_assets')

  return (
    <aside className="fixed left-0 top-0 z-50 flex h-screen w-52 flex-col border-r border-outline-variant/15 bg-surface-container-low">
      <div className="shrink-0 px-4 pb-3 pt-4">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-on-primary-fixed">
            <Icon name="deployed_code" filled className="text-[18px]" />
          </div>
          {productName ? (
            <div className="min-w-0">
              <div className="truncate text-sm font-bold tracking-tight text-on-surface">
                {productName}
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-xl border border-outline-variant/12 bg-surface-container px-3 py-2.5">
          <div className="text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
            批次列表
          </div>
          <div className="mt-1 text-xs leading-5 text-on-surface-variant">
            选择一个批次进入工作台
          </div>
        </div>
      </div>

      <nav className="flex min-h-0 flex-1 flex-col overflow-y-auto px-2.5 pb-3">
        <div className="mb-2 px-2">
          <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-outline">
            活跃批次
          </span>
        </div>

        <div className="flex flex-col gap-1">
          {tasks.map((task) => {
            const active = task.task_id === activeTaskId
            return (
              <div
                key={task.task_id}
                className={clsx(
                  'group flex items-center gap-2 rounded-xl px-2 py-1.5 transition-colors',
                  active ? 'bg-primary/10' : 'hover:bg-surface-container/55',
                )}
              >
                <button
                  onClick={() => onSelectTask(task.task_id)}
                  className="min-w-0 flex-1 rounded-lg px-2 py-1.5 text-left"
                >
                  <div
                    className={clsx(
                      'truncate text-[0.88rem] font-semibold',
                      active ? 'text-on-surface' : 'text-on-surface-variant',
                    )}
                  >
                    {task.task_name}
                  </div>
                  <div className="mt-0.5 flex items-center gap-2 text-[11px] text-outline">
                    <span>{task.item_count} 条</span>
                    <span>{task.status === 'completed' ? '已完成' : task.status === 'in_progress' ? '进行中' : '待开始'}</span>
                  </div>
                </button>

                <button
                  onClick={() => void onDeleteTask(task.task_id)}
                  className="opacity-0 rounded-lg p-1.5 text-outline transition-all hover:bg-error/10 hover:text-error group-hover:opacity-100"
                  title="删除批次"
                >
                  <Icon name="delete" className="text-[16px]" />
                </button>
              </div>
            )
          })}

          {tasks.length === 0 ? (
            <p className="px-3 py-2 text-sm text-outline">暂无批次</p>
          ) : null}
        </div>
      </nav>

      <div className="shrink-0 border-t border-outline-variant/10 px-2.5 pb-3 pt-3">
        <button
          onClick={() => setCreating(true)}
          className="mb-2 flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-3 py-2.5 text-[0.88rem] font-bold text-on-primary-fixed transition-all hover:bg-primary-dim active:scale-[0.99]"
        >
          <Icon name="add_box" className="text-[18px]" />
          创建批次
        </button>
        <button
          onClick={onOpenSettings}
          className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
        >
          <Icon name="settings" className="text-[18px]" />
          设置
        </button>
      </div>

      {creating ? (
        <div className="absolute inset-0 z-10 flex items-end bg-black/30 p-3 backdrop-blur-sm">
          <form
            className="w-full rounded-xl bg-surface-container-high p-4 shadow-xl"
            onSubmit={async (event) => {
              event.preventDefault()
              await onCreateTask({
                task_name: taskName || '未命名批次',
                project_background: projectBackground,
                style_requirements: styleRequirements,
                asset_domain: assetDomain,
              })
              setTaskName('')
              setProjectBackground('')
              setStyleRequirements('')
              setAssetDomain('game_icon_assets')
              setCreating(false)
            }}
          >
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-bold text-on-surface">新建批次</h3>
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="rounded p-1 text-on-surface-variant hover:bg-surface-container"
              >
                <Icon name="close" className="text-base" />
              </button>
            </div>
            <div className="space-y-3">
              <input
                value={taskName}
                onChange={(event) => setTaskName(event.target.value)}
                className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm outline-none ring-1 ring-transparent focus:ring-primary/40"
                placeholder="批次名称"
              />
              <textarea
                value={projectBackground}
                onChange={(event) => setProjectBackground(event.target.value)}
                className="min-h-20 w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm outline-none ring-1 ring-transparent focus:ring-primary/40"
                placeholder="项目背景"
              />
              <textarea
                value={styleRequirements}
                onChange={(event) => setStyleRequirements(event.target.value)}
                className="min-h-16 w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm outline-none ring-1 ring-transparent focus:ring-primary/40"
                placeholder="统一风格要求"
              />
              <input
                value={assetDomain}
                onChange={(event) => setAssetDomain(event.target.value)}
                className="w-full rounded-xl bg-surface-container-lowest px-3 py-2 text-sm outline-none ring-1 ring-transparent focus:ring-primary/40"
                placeholder="资产域"
              />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="rounded px-3 py-2 text-xs text-on-surface-variant hover:bg-surface-container"
              >
                取消
              </button>
              <button
                type="submit"
                className="rounded-xl bg-primary px-3 py-2 text-xs font-bold text-on-primary-fixed"
              >
                创建
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </aside>
  )
}

export { Icon }
