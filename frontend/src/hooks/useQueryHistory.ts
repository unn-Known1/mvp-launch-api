import { useState, useEffect, useCallback } from "react"
import { getQueryHistory, type NLQueryResult } from "../services/api"

interface UseQueryHistoryOptions {
  userId: string
  limit?: number
  autoFetch?: boolean
}

interface UseQueryHistoryResult {
  queries: NLQueryResult[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

export function useQueryHistory({
  userId,
  limit = 10,
  autoFetch = true,
}: UseQueryHistoryOptions): UseQueryHistoryResult {
  const [queries, setQueries] = useState<NLQueryResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!userId) return
    setLoading(true)
    setError(null)
    try {
      const data = await getQueryHistory(userId, limit)
      setQueries(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch query history")
    } finally {
      setLoading(false)
    }
  }, [userId, limit])

  useEffect(() => {
    if (!autoFetch || !userId) return
    let cancelled = false

    async function fetch() {
      setLoading(true)
      setError(null)
      try {
        const data = await getQueryHistory(userId, limit)
        if (!cancelled) setQueries(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to fetch query history")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => {
      cancelled = true
    }
  }, [autoFetch, userId, limit])

  return { queries, loading, error, refetch }
}
