import { useRef, useEffect, useCallback } from "react"
import * as echarts from "echarts"
import type { EChartsOption } from "echarts"
import { suggestChartType, type ChartData, type ChartType } from "./chartUtils"

interface ChartProps {
  data: ChartData
  type?: ChartType
  title?: string
  className?: string
}

export function Chart({ data, type, title, className }: ChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)

  const getOptions = useCallback((): EChartsOption => {
    const chartType = type || suggestChartType(data)
    const { columns, rows } = data

    if (chartType === "pie") {
      const labelCol = columns[0]
      const valueCol = columns[1] || columns[0]
      return {
        title: title ? { text: title } : undefined,
        tooltip: { trigger: "item" },
        series: [
          {
            type: "pie",
            radius: "50%",
            data: rows.map((r) => ({
              name: String(r[labelCol]),
              value: Number(r[valueCol]) || 0,
            })),
          },
        ],
      }
    }

    if (chartType === "scatter") {
      return {
        title: title ? { text: title } : undefined,
        xAxis: { type: "value" },
        yAxis: { type: "value" },
        series: [
          {
            type: "scatter",
            data: rows.map((r) => [Number(r[columns[0]]) || 0, Number(r[columns[1]]) || 0]),
          },
        ],
      }
    }

    const categoryCol = columns[0]
    const valueCols = columns.slice(1)

    return {
      title: title ? { text: title } : undefined,
      tooltip: { trigger: "axis" },
      legend: valueCols.length > 1 ? { data: valueCols } : undefined,
      xAxis: {
        type: "category",
        data: rows.map((r) => String(r[categoryCol])),
      },
      yAxis: { type: "value" },
      series: valueCols.map((col) => ({
        name: col,
        type: chartType,
        data: rows.map((r) => Number(r[col]) || 0),
      })),
    }
  }, [data, type, title])

  useEffect(() => {
    if (!chartRef.current) return

    const chart = echarts.init(chartRef.current)
    chart.setOption(getOptions())

    const handleResize = () => chart.resize()
    window.addEventListener("resize", handleResize)

    return () => {
      window.removeEventListener("resize", handleResize)
      chart.dispose()
    }
  }, [getOptions])

  return <div ref={chartRef} className={className || "w-full h-80"} />
}
