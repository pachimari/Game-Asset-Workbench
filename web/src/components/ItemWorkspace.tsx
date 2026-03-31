import { useState } from 'react'
import clsx from 'clsx'
import type { CandidateVersion, ItemSummary, WorkspacePayload } from '../types'
import { formatRelativeDate, statusLabel } from '../lib/display'
import { Icon } from './Sidebar'

type OutputTab = 'overview' | 'brief' | 'prompt' | 'candidate'

function modelLabel(value: string | null | undefined) {
  if (!value) return '继承默认'
  return value.replace(/^models\//, '')
}

function outputRecord(snapshot: WorkspacePayload['brief' | 'prompt']) {
  return (snapshot?.output ?? {}) as Record<string, unknown>
}

function inputRecord(snapshot: WorkspacePayload['brief' | 'prompt']) {
  return (snapshot?.input ?? {}) as Record<string, unknown>
}

function stringList(value: unknown) {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string')
}

function CandidateCard({ version }: { version: CandidateVersion }) {
  const firstImage = version.candidates[0]?.image_url
  const asyncStatus = version.async_job?.status
  const progress = Number(version.async_job?.progress ?? 0)

  return (
    <div className="overflow-hidden rounded border border-outline-variant/10 bg-surface-container">
      <div className="flex items-center justify-between border-b border-outline-variant/10 px-3 py-2">
        <div>
          <p className="text-[0.6875rem] font-bold text-on-surface">
            第 {Number(version.version.replace(/^v/, '')) || version.version} 次生成
          </p>
          <p className="text-[0.5rem] text-on-surface-variant">
            {modelLabel(version.model)} · {formatRelativeDate(version.created_at)}
          </p>
        </div>
        {version.is_current ? (
          <span className="rounded bg-primary/10 px-2 py-0.5 text-[0.5rem] font-bold text-primary">
            当前采用
          </span>
        ) : null}
      </div>
      {firstImage ? (
        <img src={firstImage} alt={version.version} className="aspect-square w-full object-cover" />
      ) : asyncStatus ? (
        <div className="flex aspect-square flex-col items-center justify-center gap-3 bg-primary/5">
          <Icon name="sync" className="animate-spin text-2xl text-primary-dim" />
          <div className="text-center">
            <p className="text-[0.6875rem] font-bold text-on-surface">
              {asyncStatus === 'queued' || asyncStatus === 'pending'
                ? '排队中'
                : asyncStatus === 'failed'
                  ? '生成失败'
                  : '生成中'}
            </p>
            <p className="mt-1 text-[0.5rem] text-on-surface-variant">
              进度 {Number.isFinite(progress) ? progress : 0}%
            </p>
          </div>
        </div>
      ) : (
        <div className="flex aspect-square items-center justify-center bg-surface-container-lowest text-on-surface-variant">
          <Icon name="image" className="text-2xl" />
        </div>
      )}
    </div>
  )
}

export default function ItemWorkspace({
  item,
  workspace,
  actionBusy,
  actionError,
  taskName,
  onBackToDashboard,
  onRunStep,
  onApproveStep,
  onRollbackStep,
  onPollImage,
  onCancelImage,
}: {
  item: ItemSummary
  workspace: WorkspacePayload
  actionBusy: boolean
  actionError: string | null
  taskName: string
  onBackToDashboard: () => void
  onRunStep: (step: 'brief_generation' | 'image_prompt' | 'image_generation') => void
  onApproveStep: (step: 'brief_generation' | 'image_prompt' | 'image_generation') => void
  onRollbackStep: (step: 'brief_generation' | 'image_prompt' | 'image_generation') => void
  onPollImage: (version?: string) => void
  onCancelImage: () => void
}) {
  const [outputTab, setOutputTab] = useState<OutputTab>('overview')

  const briefOutput = outputRecord(workspace?.brief ?? null)
  const promptOutput = outputRecord(workspace?.prompt ?? null)
  const candidateVersions = workspace?.candidate_pool.versions ?? []
  const approvedUrl = workspace?.candidate_pool.approved_image_url
  const selectedVersion = candidateVersions.find((v) => v.is_current) ?? candidateVersions[0]
  const pendingVersions = candidateVersions.filter((v) => {
    const status = v.async_job?.status?.toLowerCase()
    return status && ['queued', 'pending', 'running', 'processing', 'in_progress'].includes(status)
  })

  function stageActionBar() {
    switch (workspace.status) {
      case 'draft':
        return {
          primaryLabel: '生成设计说明',
          primaryAction: () => onRunStep('brief_generation'),
          secondaryLabel: null,
          secondaryAction: null,
        }
      case 'brief_generated':
        return {
          primaryLabel: '通过设计说明',
          primaryAction: () => onApproveStep('brief_generation'),
          secondaryLabel: '重新生成设计说明',
          secondaryAction: () => onRunStep('brief_generation'),
        }
      case 'brief_approved':
        return {
          primaryLabel: '生成出图指令',
          primaryAction: () => onRunStep('image_prompt'),
          secondaryLabel: '回到设计说明',
          secondaryAction: () => onRollbackStep('brief_generation'),
        }
      case 'prompt_generated':
        return {
          primaryLabel: '通过出图指令',
          primaryAction: () => onApproveStep('image_prompt'),
          secondaryLabel: '重新生成出图指令',
          secondaryAction: () => onRunStep('image_prompt'),
        }
      case 'prompt_approved':
        return {
          primaryLabel: '生成候选图',
          primaryAction: () => onRunStep('image_generation'),
          secondaryLabel: '回到出图指令',
          secondaryAction: () => onRollbackStep('image_prompt'),
        }
      case 'image_generating':
        return {
          primaryLabel: '检查生成状态',
          primaryAction: () => onPollImage(),
          secondaryLabel: '停止等待这些任务',
          secondaryAction: () => onCancelImage(),
        }
      case 'image_generated':
        return {
          primaryLabel: '通过当前候选图',
          primaryAction: () => onApproveStep('image_generation'),
          secondaryLabel: '再生成一张候选图',
          secondaryAction: () => onRunStep('image_generation'),
        }
      case 'failed':
        return {
          primaryLabel: '再生成一张候选图',
          primaryAction: () => onRunStep('image_generation'),
          secondaryLabel: '回到出图指令',
          secondaryAction: () => onRollbackStep('image_prompt'),
        }
      case 'completed':
        return {
          primaryLabel: '再生成一张候选图',
          primaryAction: () => onRunStep('image_generation'),
          secondaryLabel: '回到出图指令',
          secondaryAction: () => onRollbackStep('image_prompt'),
        }
      default:
        return {
          primaryLabel: null,
          primaryAction: null,
          secondaryLabel: null,
          secondaryAction: null,
        }
    }
  }

  const actionBar = stageActionBar()

  const tabs = [
    ['overview', '总览'],
    ['brief', '设计说明'],
    ['prompt', '出图指令'],
    ['candidate', '候选池'],
  ] as const

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col overflow-hidden bg-surface">
      <div className="shrink-0 border-b border-outline-variant/10 bg-surface-container-low/92 px-4 py-3 backdrop-blur-xl">
        <div className="flex items-center justify-between gap-3">
          <button
            onClick={onBackToDashboard}
            className="inline-flex items-center gap-2 rounded-lg border border-outline-variant/14 bg-surface-container px-3 py-1.5 text-xs font-semibold text-on-surface transition-colors hover:border-primary/25 hover:text-primary"
          >
            <Icon name="arrow_back" className="text-[16px]" />
            返回批次
          </button>
          <div className="min-w-0 text-right">
            <div className="truncate text-[11px] uppercase tracking-[0.16em] text-outline">
              {taskName || '当前批次'}
            </div>
            <div className="truncate text-sm font-bold text-on-surface">{item.title}</div>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-4 overflow-hidden p-4">
      {/* Left Pane: Original Requirements */}
      <section className="flex min-h-0 w-72 flex-col gap-4 overflow-y-auto pr-1">
        <div className="rounded-md bg-surface-container-low p-4">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
              原始需求
            </h3>
            <Icon name="info" className="text-sm text-primary" />
          </div>
          <div className="space-y-5">
            <div>
              <label className="mb-1 block text-[0.625rem] uppercase tracking-tight text-on-surface-variant">
                条目名称
              </label>
              <p className="text-lg font-bold text-on-surface">{item.title}</p>
            </div>
            <div>
              <label className="mb-1 block text-[0.625rem] uppercase tracking-tight text-on-surface-variant">
                类别
              </label>
              <span className="inline-flex rounded bg-secondary-container px-2 py-0.5 text-[0.6875rem] font-bold text-on-secondary-container">
                {item.category}
              </span>
            </div>
            <div>
              <label className="mb-1 block text-[0.625rem] uppercase tracking-tight text-on-surface-variant">
                描述
              </label>
              <p className="text-sm leading-relaxed text-on-surface">{item.description}</p>
            </div>
            {item.extra_context ? (
              <div className="rounded border-l-2 border-primary-dim/30 bg-surface-container p-3">
                <label className="mb-1 block text-[0.625rem] uppercase tracking-tight text-primary">
                  补充说明
                </label>
                <p className="text-xs italic leading-relaxed text-on-surface-variant">
                  {item.extra_context}
                </p>
              </div>
            ) : null}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded border border-outline-variant/15 bg-surface-container p-3">
                <p className="mb-1 text-on-surface-variant text-[0.625rem]">宽高比</p>
                <p className="text-xs font-semibold text-on-surface">
                  {item.runtime_overrides.image_aspect_ratio || '继承批次'}
                </p>
              </div>
              <div className="rounded border border-outline-variant/15 bg-surface-container p-3">
                <p className="mb-1 text-on-surface-variant text-[0.625rem]">分辨率</p>
                <p className="text-xs font-semibold text-on-surface">
                  {item.runtime_overrides.image_resolution || '继承批次'}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Model Info */}
        <div className="rounded-md bg-surface-container-low p-4">
          <h3 className="mb-4 text-xs font-bold uppercase tracking-widest text-on-surface-variant">
            当前条目模型
          </h3>
          <div className="space-y-2">
            {(
              [
                ['设计说明', item.model_overrides.brief_generation],
                ['出图指令', item.model_overrides.image_prompt],
                ['候选图', item.model_overrides.image_generation],
              ] as const
            ).map(([label, override]) => (
              <div
                key={label}
                className="flex items-center justify-between rounded border border-outline-variant/10 bg-surface-container p-3"
              >
                <div>
                  <p className="text-[0.625rem] text-on-surface-variant">{label}</p>
                  <p className="text-xs font-semibold text-on-surface">{modelLabel(override.model)}</p>
                </div>
                <span className="text-[0.5rem] text-outline">{override.provider || '默认'}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Events */}
        <div className="rounded-md bg-surface-container-low p-4">
          <div className="mb-4 flex items-center gap-2">
            <Icon name="schedule" className="text-sm text-primary" />
            <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
              事件日志
            </h3>
          </div>
          <div className="space-y-2">
            {workspace.events.length === 0 ? (
              <p className="text-xs text-on-surface-variant">暂无事件</p>
            ) : (
              workspace.events
                .slice()
                .reverse()
                .slice(0, 8)
                .map((event, i) => (
                  <div
                    key={`${String(event.timestamp ?? '')}-${i}`}
                    className="rounded border border-outline-variant/8 bg-surface-container p-3"
                  >
                    <p className="text-[0.6875rem] font-semibold text-on-surface">
                      {String(event.action ?? '未知动作')}
                    </p>
                    <p className="mt-0.5 text-[0.5rem] text-on-surface-variant">
                      {formatRelativeDate(String(event.timestamp ?? ''))}
                    </p>
                  </div>
                ))
            )}
          </div>
        </div>
      </section>

      {/* Center Pane: Output Canvas */}
      <section className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden">
        {/* Tabs */}
        <div className="flex w-fit items-center gap-1 rounded bg-surface-container-low p-1">
          {tabs.map(([value, label]) => (
            <button
              key={value}
              onClick={() => setOutputTab(value)}
              className={clsx(
                'rounded px-4 py-1.5 text-xs font-medium transition-colors',
                outputTab === value
                  ? 'bg-surface-container-highest text-primary'
                  : 'text-on-surface-variant hover:text-on-surface',
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto pr-1">
          {outputTab === 'overview' && (
            <>
              {/* Hero: current adopted image */}
              <div className="group relative overflow-hidden rounded-md border border-outline-variant/10 bg-surface-container-lowest">
                <div className="absolute left-4 top-4 z-10">
                  <span className="rounded bg-primary px-2 py-1 text-[0.625rem] font-black uppercase tracking-widest text-on-primary-fixed">
                    当前采用
                  </span>
                </div>
                {approvedUrl || selectedVersion?.candidates[0]?.image_url ? (
                  <img
                    src={approvedUrl || selectedVersion?.candidates[0]?.image_url || ''}
                    alt="当前采用"
                    className="h-[320px] w-full object-cover opacity-80 transition-opacity group-hover:opacity-100"
                  />
                ) : (
                  <div className="flex h-[320px] flex-col items-center justify-center bg-surface-container-lowest">
                    <Icon name="image" className="mb-3 text-4xl text-outline" />
                    <p className="text-sm text-on-surface-variant">还没有候选图</p>
                  </div>
                )}
                {approvedUrl || selectedVersion ? (
                  <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-surface-container-lowest to-transparent p-4">
                    <div className="flex items-end justify-between">
                      <div>
                        <p className="mb-1 text-[0.625rem] uppercase text-on-surface-variant">
                          {item.item_id}
                        </p>
                        <h4 className="text-base font-bold text-on-surface">
                          {selectedVersion?.version ? `V${selectedVersion.version.replace(/^v/, '')} 候选` : '已确认'}
                        </h4>
                      </div>
                      <div className="flex gap-2">
                        <button className="rounded border border-outline-variant/20 bg-surface-bright/20 p-2 backdrop-blur-md hover:bg-surface-bright/40">
                          <Icon name="fullscreen" className="text-sm" />
                        </button>
                        <button className="rounded border border-outline-variant/20 bg-surface-bright/20 p-2 backdrop-blur-md hover:bg-surface-bright/40">
                          <Icon name="download" className="text-sm" />
                        </button>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>

              {/* Generation progress slots */}
              {pendingVersions.length > 0 ? (
                <div className="grid grid-cols-3 gap-4">
                  {pendingVersions.slice(0, 3).map((version) => (
                    <div
                      key={version.version}
                      className="relative flex aspect-[4/3] flex-col items-center justify-center overflow-hidden rounded-md border-2 border-dashed border-outline-variant/20 bg-surface-container-low"
                    >
                      <div className="absolute inset-0 animate-pulse bg-primary/5" />
                      <Icon name="sync" className="animate-spin text-3xl text-primary-dim" />
                      <span className="mt-2 text-[0.6875rem] font-bold text-on-surface">
                        第 {Number(version.version.replace(/^v/, '')) || version.version} 次生成中
                      </span>
                      <span className="mt-1 text-[0.55rem] text-on-surface-variant">
                        进度 {version.async_job?.progress ?? 0}%
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}

              {/* Design Spec card inline */}
              <div className="rounded-md border-l-2 border-primary bg-surface-container-low p-5">
                <div className="mb-4 flex items-center gap-2">
                  <Icon name="architecture" className="text-base text-primary" />
                  <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface">
                    设计说明
                  </h3>
                </div>
                <div className="grid grid-cols-3 gap-6">
                  <div className="space-y-1">
                    <label className="text-[0.625rem] uppercase text-on-surface-variant">名称</label>
                    <p className="text-xs font-semibold text-on-surface">
                      {String(briefOutput.title ?? item.title)}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[0.625rem] uppercase text-on-surface-variant">视觉焦点</label>
                    <p className="text-xs font-semibold text-on-surface">
                      {String(briefOutput.visual_focus ?? '暂无')}
                    </p>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[0.625rem] uppercase text-on-surface-variant">关键词</label>
                    <div className="flex flex-wrap gap-1">
                      {stringList(briefOutput.keywords).length > 0 ? (
                        stringList(briefOutput.keywords).map((kw) => (
                          <span
                            key={kw}
                            className="rounded border border-primary/10 bg-surface-container-highest px-1 text-[0.5rem] text-primary-fixed"
                          >
                            {kw}
                          </span>
                        ))
                      ) : (
                        <span className="text-xs text-on-surface-variant">暂无</span>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}

          {outputTab === 'brief' && (
            <div className="rounded-md bg-surface-container-low p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h4 className="text-base font-bold text-on-surface">设计说明</h4>
                  <p className="mt-1 text-xs text-on-surface-variant">
                    {workspace.brief
                      ? `${workspace.brief.version} · ${modelLabel(workspace.brief.model)}`
                      : '当前还没有设计说明'}
                  </p>
                </div>
                {workspace.brief ? (
                  <span className="rounded bg-primary/10 px-2 py-0.5 text-[0.625rem] font-bold text-primary">
                    已生成
                  </span>
                ) : null}
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="rounded border border-outline-variant/10 bg-surface-container p-4">
                  <p className="mb-2 text-on-surface-variant text-xs">名称</p>
                  <p className="text-sm font-semibold text-on-surface">
                    {String(briefOutput.title ?? item.title)}
                  </p>
                </div>
                <div className="rounded border border-outline-variant/10 bg-surface-container p-4">
                  <p className="mb-2 text-on-surface-variant text-xs">视觉重点</p>
                  <p className="text-sm font-semibold text-on-surface">
                    {String(briefOutput.visual_focus ?? '暂无')}
                  </p>
                </div>
              </div>
              <div className="mt-4 rounded border border-outline-variant/10 bg-surface-container p-4">
                <p className="mb-2 text-on-surface-variant text-xs">需求整理</p>
                <p className="text-sm leading-7 text-on-surface/90">
                  {String(briefOutput.description ?? '暂无设计说明')}
                </p>
              </div>
              <div className="mt-4 rounded border border-outline-variant/10 bg-surface-container p-4">
                <p className="mb-2 text-on-surface-variant text-xs">关键词</p>
                <p className="text-sm leading-7 text-on-surface/90">
                  {stringList(briefOutput.keywords).join(' · ') || '暂无'}
                </p>
              </div>
            </div>
          )}

          {outputTab === 'prompt' && (
            <div className="rounded-md bg-surface-container-low p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <h4 className="text-base font-bold text-on-surface">出图指令</h4>
                  <p className="mt-1 text-xs text-on-surface-variant">
                    {workspace.prompt
                      ? `${workspace.prompt.version} · ${modelLabel(workspace.prompt.model)}`
                      : '当前还没有出图指令'}
                  </p>
                </div>
                {workspace.prompt ? (
                  <span className="rounded bg-secondary-container px-2 py-0.5 text-[0.625rem] font-bold text-on-secondary-container">
                    已生成
                  </span>
                ) : null}
              </div>
              <div className="space-y-4">
                <div className="rounded border border-outline-variant/10 bg-surface-container p-4">
                  <p className="mb-2 flex items-center gap-2 text-on-surface-variant text-xs">
                    <Icon name="terminal" className="text-sm" />
                    Prompt
                  </p>
                  <p className="font-mono text-sm leading-7 text-on-surface/90">
                    {String(promptOutput.prompt ?? '暂无出图指令')}
                  </p>
                </div>
                <div className="rounded border border-outline-variant/10 bg-surface-container p-4">
                  <p className="mb-2 text-on-surface-variant text-xs">Negative Prompt</p>
                  <p className="font-mono text-sm leading-7 text-on-surface/90">
                    {String(promptOutput.negative_prompt ?? '暂无')}
                  </p>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="rounded border border-outline-variant/10 bg-surface-container p-4">
                    <p className="mb-2 text-on-surface-variant text-xs">来源设计说明</p>
                    <p className="text-sm font-semibold text-on-surface">
                      {String(inputRecord(workspace.prompt).brief_version ?? '暂无')}
                    </p>
                  </div>
                  <div className="rounded border border-outline-variant/10 bg-surface-container p-4">
                    <p className="mb-2 text-on-surface-variant text-xs">当前模型</p>
                    <p className="text-sm font-semibold text-on-surface">
                      {modelLabel(workspace.prompt?.model)}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {outputTab === 'candidate' && (
            <div className="space-y-4">
              {/* Current adopted hero */}
              <div className="overflow-hidden rounded-md border border-outline-variant/10 bg-surface-container-low p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div>
                    <h4 className="text-base font-bold text-on-surface">当前采用</h4>
                    <p className="mt-1 text-xs text-on-surface-variant">已按真实候选池展示当前采用图</p>
                  </div>
                  <span className={clsx(
                    'rounded px-2 py-0.5 text-[0.625rem] font-bold',
                    statusLabel(item.status) === '已完成'
                      ? 'bg-tertiary/10 text-tertiary'
                      : 'bg-primary/10 text-primary',
                  )}>
                    {statusLabel(item.status)}
                  </span>
                </div>
                {approvedUrl ? (
                  <img src={approvedUrl} alt="approved" className="aspect-[16/10] w-full rounded object-cover" />
                ) : (
                  <div className="flex aspect-[16/10] items-center justify-center rounded border border-dashed border-primary/25 bg-primary/5 text-on-surface-variant">
                    尚未确认最终候选图
                  </div>
                )}
              </div>

              {/* Candidate grid */}
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {candidateVersions.length === 0 ? (
                  <div className="col-span-full rounded border border-dashed border-outline-variant/20 bg-surface-container-high p-6 text-center text-sm text-on-surface-variant">
                    当前还没有候选池内容
                  </div>
                ) : (
                  candidateVersions.map((v) => (
                    <CandidateCard key={v.version} version={v} />
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Bottom quick actions */}
        <div className="glass-panel flex items-center justify-between rounded-md border border-outline-variant/15 p-3">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 animate-pulse rounded-full bg-tertiary" />
              <span className="text-[0.6875rem] font-bold text-on-surface">
                阶段: {statusLabel(item.status)}
              </span>
            </div>
            {actionError ? (
              <span className="rounded bg-error-container px-2 py-1 text-[0.625rem] text-on-error-container">
                {actionError}
              </span>
            ) : null}
          </div>
          <div className="flex gap-2">
            {actionBar.secondaryLabel ? (
              <button
                disabled={actionBusy}
                onClick={actionBar.secondaryAction ?? undefined}
                className="rounded bg-surface-container-highest px-4 py-1.5 text-[0.6875rem] font-bold uppercase text-on-surface transition-colors hover:bg-surface-bright disabled:cursor-not-allowed disabled:opacity-50"
              >
                {actionBar.secondaryLabel}
              </button>
            ) : null}
            {actionBar.primaryLabel ? (
              <button
                disabled={actionBusy}
                onClick={actionBar.primaryAction ?? undefined}
                className="rounded bg-primary px-4 py-1.5 text-[0.6875rem] font-bold uppercase text-on-primary-fixed transition-colors hover:bg-primary-dim disabled:cursor-not-allowed disabled:opacity-50"
              >
                {actionBusy ? '处理中…' : actionBar.primaryLabel}
              </button>
            ) : null}
          </div>
        </div>
      </section>

      {/* Right Pane: Chat & Version History */}
      <section className="flex min-h-0 w-80 flex-col gap-4 overflow-y-auto pl-1">
        {/* Chat Control */}
        <div className="flex min-h-[300px] flex-1 flex-col overflow-hidden rounded-md bg-surface-container-low">
          <div className="flex items-center justify-between bg-surface-container-highest px-4 py-2">
            <h3 className="text-[0.625rem] font-black uppercase tracking-widest text-primary-fixed">
              聊天控制
            </h3>
            <Icon name="terminal" className="text-sm opacity-40" />
          </div>
          <div className="flex-1 space-y-4 overflow-y-auto p-4 text-[0.6875rem]">
            {workspace.chat.length === 0 ? (
              <p className="text-center text-xs text-on-surface-variant">暂无聊天记录</p>
            ) : (
              workspace.chat.slice(-10).map((msg, i) => {
                const isUser = String(msg.role ?? '') === 'user'
                return (
                  <div
                    key={i}
                    className={clsx(
                      'flex max-w-[90%] flex-col gap-1',
                      isUser ? 'ml-auto items-end' : 'items-start',
                    )}
                  >
                    <div
                      className={clsx(
                        'rounded p-2 text-on-surface-variant leading-normal',
                        isUser
                          ? 'border border-primary/20 bg-primary-container/20 text-on-primary-container'
                          : 'bg-surface-container',
                      )}
                    >
                      {String(msg.content ?? msg.message ?? '')}
                    </div>
                    <span className="text-[0.5rem] opacity-30">
                      {isUser ? 'YOU' : 'SYSTEM'}
                    </span>
                  </div>
                )
              })
            )}
          </div>
          <div className="border-t border-outline-variant/10 bg-surface-container p-2">
            <div className="relative">
              <input
                className="w-full rounded bg-surface-container-highest py-2 pl-3 pr-10 text-[0.6875rem] text-on-surface outline-none placeholder:text-outline focus:ring-1 focus:ring-primary"
                placeholder="输入控制指令..."
              />
              <Icon
                name="send"
                filled
                className="absolute right-2 top-1.5 cursor-pointer text-lg text-primary"
              />
            </div>
          </div>
        </div>

        {/* Version History */}
        <div className="rounded-md bg-surface-container-low p-4">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-widest text-on-surface-variant">
              版本历史
            </h3>
            <button className="text-[0.625rem] text-primary hover:underline">查看全部</button>
          </div>
          <div className="space-y-3">
            {candidateVersions.length === 0 ? (
              <p className="text-xs text-on-surface-variant">暂无版本</p>
            ) : (
              candidateVersions.slice(0, 5).map((v) => (
                <div key={v.version} className="flex cursor-pointer items-center gap-3">
                  <div className="h-8 w-8 overflow-hidden rounded bg-surface-container-lowest">
                    {v.candidates[0]?.image_url ? (
                      <img src={v.candidates[0].image_url} alt={v.version} className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center">
                        <Icon name="image" className="text-xs text-outline" />
                      </div>
                    )}
                  </div>
                  <div>
                    <p className={clsx(
                      'text-[0.625rem] font-bold',
                      v.is_current ? 'text-on-surface' : 'text-on-surface-variant',
                    )}>
                      {v.version} {v.is_current ? '- 当前' : ''}
                    </p>
                    <p className="text-[0.5rem] text-on-surface-variant">
                      {formatRelativeDate(v.created_at)}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
      </div>
    </div>
  )
}
