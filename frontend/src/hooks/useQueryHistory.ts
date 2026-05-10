import { useState, useEffect, useCallback, useRef } from "react"
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

function createError(message: string, cause?: Error): Error {
  const err = new Error(message)
  if (cause) err.cause = cause
  return err
}

export function useQueryHistory({
  userId,
  limit = 10,
  autoFetch = true,
}: UseQueryHistoryOptions): UseQueryHistoryResult {
  const [queries, setQueries] = useState<NLQueryResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const userIdRef = useRef(userId)
  const limitRef = useRef(limit)

  // Keep refs fresh
  useEffect(() => {
    userIdRef.current = userId
    limitRef.current = limit
  }, [userId, limit])

  const refetch = useCallback(async () => {
    if (!userIdRef.current) return
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    setLoading(true)
    setError(null)
    try {
      const data = await getQueryHistory(userIdRef.current, limitRef.current, abortControllerRef.current.signal)
      setQueries(data)
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return
      }
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch query history"
      setError(errorMessage)
      throw createError(errorMessage, err instanceof Error ? err : undefined)
    } finally {
      setLoading(false)
    }
  }, []) // No deps - uses refs

  useEffect(() => {
    if (!autoFetch || !userIdRef.current) return

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
        const data = await getQueryHistory(userIdRef.current, limitRef.current, abortController.signal)
        if (!cancelled) setQueries(data)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        const errorMessage = err instanceof Error ? err.message : "Failed to fetch query history"
        if (!cancelled) {
          setError(errorMessage)
          console.error("[useQueryHistory] Fetch error:", err)
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
  }, [autoFetch, userIdRef, limitRef]) // Use refs

  return { queries, loading, error, refetch }
}
