const stageLabelMap: Record<string, string> = {
  draft: '待开始',
  in_progress: '进行中',
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

export function statusLabel(status: string) {
  return stageLabelMap[status] ?? status
}

export function formatRelativeDate(value: string | null | undefined) {
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
