export interface ChartData {
  columns: string[]
  rows: Record<string, unknown>[]
}

export type ChartType = "line" | "bar" | "pie" | "scatter"

export function suggestChartType(data: ChartData): ChartType {
  const { columns, rows } = data
  if (columns.length < 2) return "bar"

  const firstCol = columns[0]
  const secondCol = columns[1]

  const firstVal = rows[0]?.[firstCol]
  const secondVal = rows[0]?.[secondCol]
  const isDate = firstVal && !isNaN(Date.parse(String(firstVal)))
  const isNumeric = secondVal && !isNaN(Number(secondVal))

  if (isDate && isNumeric) return "line"
  if (isNumeric) return "bar"

  const uniqueValues = new Set(rows.map((r) => r[secondCol]))
  if (uniqueValues.size <= 10) return "pie"

  return "bar"
}
