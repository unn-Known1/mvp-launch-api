import { useState, useEffect, useCallback } from "react"
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

export function useScheduledReports({
  userId,
  isActive,
  autoFetch = true,
}: UseScheduledReportsOptions): UseScheduledReportsResult {
  const [reports, setReports] = useState<ScheduledReport[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    if (!userId) return
    setLoading(true)
    setError(null)
    try {
      const data = await listScheduledReports(userId, isActive)
      setReports(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch scheduled reports")
    } finally {
      setLoading(false)
    }
  }, [userId, isActive])

  useEffect(() => {
    if (!autoFetch || !userId) return
    let cancelled = false

    async function fetch() {
      setLoading(true)
      setError(null)
      try {
        const data = await listScheduledReports(userId, isActive)
        if (!cancelled) setReports(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to fetch scheduled reports")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => {
      cancelled = true
    }
  }, [autoFetch, userId, isActive])

  return { reports, loading, error, refetch }
}
