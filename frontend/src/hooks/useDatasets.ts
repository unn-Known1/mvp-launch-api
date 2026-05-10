import { useState, useEffect, useCallback, useRef } from "react"
import { listDatasets, type Dataset, type DatasetsListResponse } from "../services/api"

interface UseDatasetsOptions {
  page?: number
  limit?: number
  autoFetch?: boolean
}

interface UseDatasetsResult {
  datasets: Dataset[]
  total: number
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

function createError(message: string, cause?: Error): Error {
  const err = new Error(message)
  if (cause) err.cause = cause
  return err
}

export function useDatasets({
  page = 1,
  limit = 20,
  autoFetch = true,
}: UseDatasetsOptions = {}): UseDatasetsResult {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const pageRef = useRef(page)
  const limitRef = useRef(limit)

  // Keep refs fresh
  useEffect(() => {
    pageRef.current = page
    limitRef.current = limit
  }, [page, limit])

  const refetch = useCallback(async () => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    setLoading(true)
    setError(null)
    try {
      const response: DatasetsListResponse = await listDatasets(pageRef.current, limitRef.current, abortControllerRef.current.signal)
      setDatasets(response.data || [])
      setTotal(response.total || 0)
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return
      }
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch datasets"
      setError(errorMessage)
      throw createError(errorMessage, err instanceof Error ? err : undefined)
    } finally {
      setLoading(false)
    }
  }, []) // No deps - uses refs

  useEffect(() => {
    if (!autoFetch) return

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
        const response: DatasetsListResponse = await listDatasets(pageRef.current, limitRef.current, abortController.signal)
        if (!cancelled) {
          setDatasets(response.data || [])
          setTotal(response.total || 0)
        }
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        const errorMessage = err instanceof Error ? err.message : "Failed to fetch datasets"
        if (!cancelled) {
          setError(errorMessage)
          console.error("[useDatasets] Fetch error:", err)
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
  }, [autoFetch, pageRef, limitRef])

  return { datasets, total, loading, error, refetch }
}
