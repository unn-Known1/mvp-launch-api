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

export function QueryResultDisplay({ result }: QueryResultDisplayProps) {
  const [viewMode, setViewMode] = useState<ViewMode>("chart")
  const [chartType, setChartType] = useState<ChartType>("line")

  if (!result.results || result.results.length === 0) {
    return (
      <Card>
        <CardContent className="py-8 text-center text-muted-foreground">
          No results to display
        </CardContent>
      </Card>
    )
  }

  const columns = Object.keys(result.results[0])
  const chartData: ChartData = {
    columns,
    rows: result.results,
  }

  const columnDefs = columns.map((col) => ({
    key: col as keyof typeof result.results[0],
    header: col,
  }))

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>Query Results</CardTitle>
          <div className="flex gap-2">
            <Select value={chartType} onValueChange={(v) => setChartType(v as ChartType)}>
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
