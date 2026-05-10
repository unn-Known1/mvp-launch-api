import { useRef, useEffect, useCallback } from "react"
import type { EChartsOption } from "echarts"
import { suggestChartType, type ChartData, type ChartType } from "./chartUtils"

// Cache echarts import to avoid re-importing on every render
let echartsModule: typeof import("echarts") | null = null
let echartsInitPromise: Promise<typeof import("echarts")> | null = null

function getEcharts(): Promise<typeof import("echarts")> {
  if (echartsModule) {
    return Promise.resolve(echartsModule)
  }
  if (echartsInitPromise) {
    return echartsInitPromise
  }
  echartsInitPromise = import("echarts").then((module) => {
    echartsModule = module
    return module
  })
  return echartsInitPromise
}

interface ChartProps {
  data: ChartData
  type?: ChartType
  title?: string
  className?: string
}

export function Chart({ data, type, title, className }: ChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)
  const chartInstanceRef = useRef<any>(null)
  const resizeHandlerRef = useRef<(() => void) | null>(null)
  const mountedRef = useRef(true)

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
    mountedRef.current = true

    if (!chartRef.current) return

    let chartInstance: any = null

    const initChart = async () => {
      const echarts = await getEcharts()
      if (!chartRef.current || !mountedRef.current) return

      chartInstance = echarts.init(chartRef.current)
      chartInstanceRef.current = chartInstance
      chartInstance.setOption(getOptions())

      resizeHandlerRef.current = () => chartInstance.resize()
      window.addEventListener("resize", resizeHandlerRef.current)
    }

    initChart()

    return () => {
      mountedRef.current = false
      if (resizeHandlerRef.current) {
        window.removeEventListener("resize", resizeHandlerRef.current)
        resizeHandlerRef.current = null
      }
      if (chartInstance) {
        chartInstance.dispose()
        chartInstanceRef.current = null
      }
    }
  }, [getOptions])

  return <div ref={chartRef} className={className || "w-full h-80"} />
}
