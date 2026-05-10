import { useState, useEffect, useCallback, useRef } from "react"
import { listScheduledReports, type ScheduledReport } from "../services/api"

interface UseScheduledReportsOptions {
  userId: string
  isActive?: boolean
  autoFetch?: boolean
}

interface UseScheduledReportsResult {
  reports: ScheduledReport[]
  loading: boolean
  error: string | null
  refetch: () => Promise<void>
}

function createError(message: string, cause?: Error): Error {
  const err = new Error(message)
  if (cause) err.cause = cause
  return err
}

export function useScheduledReports({
  userId,
  isActive,
  autoFetch = true,
}: UseScheduledReportsOptions): UseScheduledReportsResult {
  const [reports, setReports] = useState<ScheduledReport[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const userIdRef = useRef(userId)
  const isActiveRef = useRef(isActive)

  // Keep refs fresh
  useEffect(() => {
    userIdRef.current = userId
    isActiveRef.current = isActive
  }, [userId, isActive])

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
      const data = await listScheduledReports(userIdRef.current, isActiveRef.current, abortControllerRef.current.signal)
      setReports(data)
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return
      }
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch scheduled reports"
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
        const data = await listScheduledReports(userIdRef.current, isActiveRef.current, abortController.signal)
        if (!cancelled) setReports(data)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        const errorMessage = err instanceof Error ? err.message : "Failed to fetch scheduled reports"
        if (!cancelled) {
          setError(errorMessage)
          console.error("[useScheduledReports] Fetch error:", err)
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
  }, [autoFetch, userIdRef, isActiveRef]) // Use refs

  return { reports, loading, error, refetch }
}
