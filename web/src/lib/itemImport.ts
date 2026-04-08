export type ImportedItemDraft = {
  title: string
  description: string
  asset_type: string
  category: string
  extra_context: string
  image_aspect_ratio?: string | null
  image_resolution?: string | null
}

const headerAliases: Record<string, keyof ImportedItemDraft | ''> = {
  '名称': 'title',
  title: 'title',
  '需求描述': 'description',
  description: 'description',
  '资产类型': 'asset_type',
  asset_type: 'asset_type',
  '分类': 'category',
  category: 'category',
  '条目补充说明': 'extra_context',
  '额外上下文': 'extra_context',
  extra_context: 'extra_context',
  '宽高比': 'image_aspect_ratio',
  image_aspect_ratio: 'image_aspect_ratio',
  '分辨率': 'image_resolution',
  image_resolution: 'image_resolution',
}

function normalizeCell(value: string | undefined) {
  return (value ?? '').trim()
}

function splitCsvLine(line: string, delimiter: string) {
  const cells: string[] = []
  let current = ''
  let inQuotes = false

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index]
    const next = line[index + 1]
    if (char === '"') {
      if (inQuotes && next === '"') {
        current += '"'
        index += 1
      } else {
        inQuotes = !inQuotes
      }
      continue
    }
    if (char === delimiter && !inQuotes) {
      cells.push(current)
      current = ''
      continue
    }
    current += char
  }

  cells.push(current)
  return cells.map((cell) => cell.trim())
}

export function parseImportedItems(rawText: string): ImportedItemDraft[] {
  const text = rawText.trim()
  if (!text) return []

  const delimiter = text.includes('\t') ? '\t' : ','
  const rows = text
    .split(/\r?\n/)
    .map((line) => splitCsvLine(line, delimiter))
    .filter((row) => row.some((cell) => cell.trim()))

  if (rows.length === 0) return []

  const firstRow = rows[0].map((cell) => normalizeCell(cell))
  const normalizedHeader = firstRow.map((cell) => {
    const key = cell.toLowerCase()
    return headerAliases[cell] ?? headerAliases[key] ?? ''
  })
  const hasHeader = normalizedHeader.some(Boolean)

  const fallbackFields: Array<keyof ImportedItemDraft> = [
    'title',
    'description',
    'asset_type',
    'category',
    'extra_context',
    'image_aspect_ratio',
    'image_resolution',
  ]

  const sourceRows = hasHeader ? rows.slice(1) : rows
  const fieldMap = hasHeader ? normalizedHeader : fallbackFields

  return sourceRows
    .map((row) => {
      const payload: ImportedItemDraft = {
        title: '',
        description: '',
        asset_type: 'generic_icon',
        category: '',
        extra_context: '',
        image_aspect_ratio: null,
        image_resolution: null,
      }

      row.forEach((value, index) => {
        const field = fieldMap[index]
        if (!field) return
        const normalizedValue = normalizeCell(value)
        if (field === 'image_aspect_ratio' || field === 'image_resolution') {
          payload[field] = normalizedValue || null
          return
        }
        payload[field] = normalizedValue
      })

      if (!payload.asset_type) {
        payload.asset_type = 'generic_icon'
      }

      return payload
    })
    .filter((row) => Object.values(row).some((value) => typeof value === 'string' ? value.trim() : value))
}
