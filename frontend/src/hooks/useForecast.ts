import { useState, useEffect, useCallback } from "react"
import { getForecast, type ForecastResult } from "../services/api"
import type { ChartData } from "../components/charts/chartUtils"

interface UseForecastOptions {
  forecastId: string | null
  autoFetch?: boolean
}

interface UseForecastResult {
  forecast: ForecastResult | null
  chartData: ChartData | null
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useForecast({
  forecastId,
  autoFetch = true,
}: UseForecastOptions): UseForecastResult {
  const [forecast, setForecast] = useState<ForecastResult | null>(null)
  const [chartData, setChartData] = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!forecastId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getForecast(forecastId as string)
      setForecast(data)

      // Transform forecast data to ChartData format
      if (data.forecast && data.forecast.length > 0) {
        const firstRow = data.forecast[0]
        const columns = Object.keys(firstRow)
        setChartData({
          columns,
          rows: data.forecast as Record<string, unknown>[],
        })
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch forecast")
    } finally {
      setLoading(false)
    }
  }, [forecastId])

  useEffect(() => {
    if (!autoFetch || !forecastId) return
    let cancelled = false

    async function fetch() {
      setLoading(true)
      setError(null)
      try {
        const data = await getForecast(forecastId as string)
        if (!cancelled) {
          setForecast(data)

          // Transform forecast data to ChartData format
          if (data.forecast && data.forecast.length > 0) {
            const firstRow = data.forecast[0]
            const columns = Object.keys(firstRow)
            setChartData({
              columns,
              rows: data.forecast as Record<string, unknown>[],
            })
          }
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to fetch forecast")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => {
      cancelled = true
    }
  }, [autoFetch, forecastId])

  return { forecast, chartData, loading, error, refetch }
}
