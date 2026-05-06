import { useRef, useEffect } from "react"
import * as echarts from "echarts"

interface LineChartProps {
  data: { name: string; value: number }[]
  title?: string
  className?: string
}

export function LineChart({ data, title, className }: LineChartProps) {
  const chartRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!chartRef.current) return

    const chart = echarts.init(chartRef.current)

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

    const handleResize = () => chart.resize()
    window.addEventListener("resize", handleResize)

    return () => {
      window.removeEventListener("resize", handleResize)
      chart.dispose()
    }
  }, [data, title])

  return <div ref={chartRef} className={className || "w-full h-64"} />
}
