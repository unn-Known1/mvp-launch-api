import { useRef, useEffect } from "react"

interface LineChartProps {
  data: { name: string; value: number }[]
  title?: string
  className?: string
}

export function LineChart({ data, title, className }: LineChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartRef.current) return

    let chart: any = null
    let handleResize: (() => void) | null = null

    const initChart = async () => {
      const echarts = await import("echarts")
      if (!chartRef.current) return
      
      chart = echarts.init(chartRef.current)

      chart.setOption({
        title: title ? { text: title } : undefined,
        tooltip: { trigger: "axis" },
        xAxis: {
          type: "category",
          data: data.map((d) => d.name),
        },
        yAxis: { type: "value" },
        series: [
          {
            data: data.map((d) => d.value),
            type: "line",
          },
        ],
      })

      handleResize = () => chart.resize()
      window.addEventListener("resize", handleResize)
    }

    initChart()

    return () => {
      if (handleResize) {
        window.removeEventListener("resize", handleResize)
      }
      if (chart) {
        chart.dispose()
      }
    }
  }, [data, title])

  return <div ref={chartRef} className={className || "w-full h-64"} />
}
