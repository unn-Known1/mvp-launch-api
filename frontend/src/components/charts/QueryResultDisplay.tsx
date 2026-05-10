import { useState } from "react"
import { Chart } from "./Chart"
import type { ChartData, ChartType } from "./chartUtils"
import { DataTable } from "../tables/DataTable"
import { Button } from "../ui/Button"
import { Card, CardHeader, CardTitle, CardContent } from "../ui/Card"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../ui/Select"
import type { NLQueryResult } from "../../services/api"

interface QueryResultDisplayProps {
  result: NLQueryResult
}

type ViewMode = "chart" | "table"

const CHART_TYPES: ChartType[] = ["line", "bar", "pie", "scatter"]

function isValidChartType(value: string): value is ChartType {
  return CHART_TYPES.includes(value as ChartType)
}

function isNonEmptyArray<T>(arr: unknown): arr is T[] {
  return Array.isArray(arr) && arr.length > 0
}

export function QueryResultDisplay({ result }: QueryResultDisplayProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("chart")
  const [chartType, setChartType] = useState<ChartType>("line")

  if (!isNonEmptyArray(result.results)) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          No results to display
        </CardContent>
      </Card>
    )
  }

  const firstRow = result.results[0]
  if (!firstRow || typeof firstRow !== 'object') {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          Invalid results data
        </CardContent>
      </Card>
    )
  }

  const columns = Object.keys(firstRow)
  const chartData: ChartData = {
    columns,
    rows: result.results as Record<string, unknown>[],
  }

  const columnDefs = columns.map((col) => ({
    key: col as keyof typeof firstRow,
    header: col,
  }))

  const handleChartTypeChange = (value: string) => {
    if (isValidChartType(value)) {
      setChartType(value)
    }
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Query Results</CardTitle>
          <div className="flex gap-2">
            <Select value={chartType} onValueChange={handleChartTypeChange}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="line">Line</SelectItem>
                <SelectItem value="bar">Bar</SelectItem>
                <SelectItem value="pie">Pie</SelectItem>
                <SelectItem value="scatter">Scatter</SelectItem>
              </SelectContent>
            </Select>
            <Button
              variant={viewMode === "chart" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("chart")}
            >
              Chart
            </Button>
            <Button
              variant={viewMode === "table" ? "default" : "outline"}
              size="sm"
              onClick={() => setViewMode("table")}
            >
              Table
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {viewMode === "chart" ? (
          <Chart data={chartData} type={chartType} title="Results" />
        ) : (
          <DataTable data={result.results} columns={columnDefs} />
        )}
        <div className="mt-4 text-sm text-muted-foreground">
          {result.row_count} rows • {result.execution_time_ms}ms • Confidence: {result.confidence_level}
        </div>
      </CardContent>
    </Card>
  )
}
