import { useState, useEffect, useCallback, useRef } from "react"
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

function createError(message: string, cause?: Error): Error {
  const err = new Error(message)
  if (cause) err.cause = cause
  return err
}

export function useForecast({
  forecastId,
  autoFetch = true,
}: UseForecastOptions): UseForecastResult {
  const [forecast, setForecast] = useState<ForecastResult | null>(null)
  const [chartData, setChartData] = useState<ChartData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const forecastIdRef = useRef(forecastId)

  // Keep refs fresh
  useEffect(() => {
    forecastIdRef.current = forecastId
  }, [forecastId])

  const refetch = useCallback(async () => {
    if (!forecastIdRef.current) return
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    setLoading(true)
    setError(null)
    try {
      const data = await getForecast(forecastIdRef.current as string, abortControllerRef.current.signal)
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
      if (err instanceof Error && err.name === 'AbortError') {
        return
      }
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch forecast"
      setError(errorMessage)
      throw createError(errorMessage, err instanceof Error ? err : undefined)
    } finally {
      setLoading(false)
    }
  }, []) // No deps - uses refs

  useEffect(() => {
    if (!autoFetch || !forecastIdRef.current) return

    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    const abortController = new AbortController()
    abortControllerRef.current = abortController
    let cancelled = false

    async function fetch() {
      setLoading(true)
      setError(null)
      try {
        const data = await getForecast(forecastIdRef.current as string, abortController.signal)
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
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        const errorMessage = err instanceof Error ? err.message : "Failed to fetch forecast"
        if (!cancelled) {
          setError(errorMessage)
          console.error("[useForecast] Fetch error:", err)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => {
      cancelled = true
      abortController.abort()
    }
  }, [autoFetch]) // Only autoFetch as dep - uses refs

  return { forecast, chartData, loading, error, refetch }
}
