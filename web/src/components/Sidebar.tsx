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
  const [createBusy, setCreateBusy] = useState(false)
  const [taskName, setTaskName] = useState('')
  const [projectBackground, setProjectBackground] = useState('')
  const [styleRequirements, setStyleRequirements] = useState('')
  const [assetDomain, setAssetDomain] = useState('game_icon_assets')

  function resetCreateDraft() {
    setTaskName('')
    setProjectBackground('')
    setStyleRequirements('')
    setAssetDomain('game_icon_assets')
  }

  async function submitCreateTask() {
    setCreateBusy(true)
    try {
      await onCreateTask({
        task_name: taskName || '未命名批次',
        project_background: projectBackground,
        style_requirements: styleRequirements,
        asset_domain: assetDomain,
      })
      resetCreateDraft()
      setCreating(false)
    } finally {
      setCreateBusy(false)
    }
  }

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
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-background/72 p-6 backdrop-blur-md">
          <button
            type="button"
            aria-label="关闭新建批次"
            className="absolute inset-0"
            onClick={() => {
              setCreating(false)
              resetCreateDraft()
            }}
          />
          <form
            className="relative z-10 w-full max-w-3xl overflow-hidden rounded-[28px] border border-outline-variant/12 bg-surface-container-low shadow-[0_30px_80px_rgba(0,0,0,0.45)]"
            onSubmit={async (event) => {
              event.preventDefault()
              await submitCreateTask()
            }}
          >
            <div className="border-b border-outline-variant/10 bg-[radial-gradient(circle_at_top_left,_rgba(161,155,255,0.16),_transparent_38%),linear-gradient(180deg,_rgba(17,26,49,0.96)_0%,_rgba(12,20,38,0.96)_100%)] px-6 py-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-outline">
                    Create Batch
                  </div>
                  <h3 className="mt-2 text-[1.8rem] font-black tracking-tight text-on-surface">
                    新建批次
                  </h3>
                  <p className="mt-2 max-w-xl text-sm leading-6 text-on-surface-variant">
                    先定义这个批次的共同背景和风格要求，后面新增的 item 默认都会在这套上下文里工作。
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setCreating(false)
                    resetCreateDraft()
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
                    <Icon name="deployed_code" filled className="text-[18px]" />
                    <span className="text-sm font-bold text-on-surface">这个批次会共享什么</span>
                  </div>
                  <div className="space-y-3 text-sm text-on-surface-variant">
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">项目背景</div>
                      <div className="mt-1 leading-6">世界观、产品语境、使用场景。</div>
                    </div>
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">统一风格要求</div>
                      <div className="mt-1 leading-6">材质、光感、边框、禁用项和整体调性。</div>
                    </div>
                    <div className="rounded-xl bg-surface-container-low px-3 py-3">
                      <div className="text-xs font-bold text-on-surface">资产域</div>
                      <div className="mt-1 leading-6">主要用于区分任务类型，默认填当前图标资产工作流即可。</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="px-6 py-6">
                <div className="space-y-4">
                  <label className="block">
                    <span className="mb-2 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                      批次名称
                    </span>
                    <input
                      value={taskName}
                      onChange={(event) => setTaskName(event.target.value)}
                      className="w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-[1.05rem] font-semibold text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                      placeholder="例如：M5 正式批量图标、四月技能图第一轮"
                      autoFocus
                    />
                  </label>

                  <label className="block">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                        项目背景
                      </span>
                      <span className="text-[11px] text-outline">可选，但建议填写</span>
                    </div>
                    <textarea
                      value={projectBackground}
                      onChange={(event) => setProjectBackground(event.target.value)}
                      className="min-h-28 w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm leading-6 text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                      placeholder="这个批次服务于什么项目、什么题材、什么场景。"
                    />
                  </label>

                  <label className="block">
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                        统一风格要求
                      </span>
                      <span className="text-[11px] text-outline">后面所有 item 默认参考它</span>
                    </div>
                    <textarea
                      value={styleRequirements}
                      onChange={(event) => setStyleRequirements(event.target.value)}
                      className="min-h-24 w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm leading-6 text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                      placeholder="例如：高对比、厚重边框、材质统一、避免文字和复杂背景。"
                    />
                  </label>

                  <label className="block">
                    <span className="mb-2 block text-[11px] font-bold uppercase tracking-[0.16em] text-outline">
                      资产域
                    </span>
                    <input
                      value={assetDomain}
                      onChange={(event) => setAssetDomain(event.target.value)}
                      className="w-full rounded-2xl border border-outline-variant/12 bg-surface-container-high px-4 py-3 text-sm text-on-surface outline-none transition-colors placeholder:text-outline focus:border-primary/35"
                      placeholder="game_icon_assets"
                    />
                  </label>
                </div>

                <div className="mt-6 flex items-center justify-between gap-3">
                  <div className="text-xs text-on-surface-variant">
                    创建后就可以往这个批次里继续加 item。
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        setCreating(false)
                        resetCreateDraft()
                      }}
                      className="rounded-xl px-4 py-2.5 text-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface"
                    >
                      取消
                    </button>
                    <button
                      type="submit"
                      disabled={createBusy}
                      className="rounded-2xl bg-primary px-5 py-2.5 text-sm font-bold text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {createBusy ? '创建中…' : '创建批次'}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </form>
        </div>
      ) : null}
    </aside>
  )
}

export { Icon }
