import { useState, useEffect, useCallback } from "react"
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

export function useDatasets({
  page = 1,
  limit = 20,
  autoFetch = true,
}: UseDatasetsOptions = {}): UseDatasetsResult {
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response: DatasetsListResponse = await listDatasets(page, limit)
      setDatasets(response.data || [])
      setTotal(response.total || 0)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch datasets")
    } finally {
      setLoading(false)
    }
  }, [page, limit])

  useEffect(() => {
    if (!autoFetch) return
    let cancelled = false

    async function fetch() {
      setLoading(true)
      setError(null)
      try {
        const response: DatasetsListResponse = await listDatasets(page, limit)
        if (!cancelled) {
          setDatasets(response.data || [])
          setTotal(response.total || 0)
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to fetch datasets")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => {
      cancelled = true
    }
  }, [autoFetch, page, limit])

  return { datasets, total, loading, error, refetch }
}
