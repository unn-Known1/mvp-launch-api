import { useState, useEffect, useCallback, useRef } from "react"
import { listAnomalies, updateAnomaly, type Anomaly } from "../services/api"

interface UseAnomaliesOptions {
  datasetId?: string
  status?: string
  severity?: string
  autoFetch?: boolean
}

interface UseAnomaliesResult {
  anomalies: Anomaly[]
  loading: boolean
  error: string | null
  updateStatus: (anomalyId: string, status: "investigated" | "dismissed", notes?: string) => Promise<void>
  refetch: () => Promise<void>
}

function createError(message: string, cause?: Error): Error {
  const err = new Error(message)
  if (cause) err.cause = cause
  return err
}

export function useAnomalies({
  datasetId,
  status,
  severity,
  autoFetch = true,
}: UseAnomaliesOptions = {}): UseAnomaliesResult {
  const [anomalies, setAnomalies] = useState<Anomaly[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const mountedRef = useRef(true)
  const abortControllerRef = useRef<AbortController | null>(null)
  // Refs to track latest values for use in callbacks without dependency issues
  const datasetIdRef = useRef(datasetId)
  const statusRef = useRef(status)
  const severityRef = useRef(severity)

  // Keep refs fresh
  useEffect(() => {
    mountedRef.current = true
    datasetIdRef.current = datasetId
    statusRef.current = status
    severityRef.current = severity
    return () => {
      mountedRef.current = false
    }
  }, [datasetId, status, severity])

  const refetch = useCallback(async () => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    setLoading(true)
    setError(null)
    try {
      const filters: { dataset_id?: string; status?: string; severity?: string } = {}
      if (datasetIdRef.current) filters.dataset_id = datasetIdRef.current
      if (statusRef.current) filters.status = statusRef.current
      if (severityRef.current) filters.severity = severityRef.current
      const data = await listAnomalies(filters, abortControllerRef.current.signal)
      if (mountedRef.current) setAnomalies(data)
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        // Request was cancelled, don't update state
        return
      }
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch anomalies"
      if (mountedRef.current) {
        setError(errorMessage)
        throw createError(errorMessage, err instanceof Error ? err : undefined)
      }
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, []) // No deps - uses refs

  const updateStatus = useCallback(
    async (anomalyId: string, newStatus: "investigated" | "dismissed", notes?: string) => {
      try {
        const updated = await updateAnomaly(anomalyId, { status: newStatus, notes })
        setAnomalies((prev) =>
          prev.map((a) => (a.id === anomalyId ? updated : a))
        )
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : "Failed to update anomaly"
        setError(errorMessage)
        throw createError(errorMessage, err instanceof Error ? err : undefined)
      }
    },
    []
  )

  // Effect to trigger initial fetch when autoFetch or filter params change
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
        const filters: { dataset_id?: string; status?: string; severity?: string } = {}
        if (datasetIdRef.current) filters.dataset_id = datasetIdRef.current
        if (statusRef.current) filters.status = statusRef.current
        if (severityRef.current) filters.severity = severityRef.current
        const data = await listAnomalies(filters, abortController.signal)
        if (!cancelled && mountedRef.current) setAnomalies(data)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          // Request was cancelled, don't update state
          return
        }
        const errorMessage = err instanceof Error ? err.message : "Failed to fetch anomalies"
        if (!cancelled && mountedRef.current) {
          setError(errorMessage)
          console.error("[useAnomalies] Fetch error:", err)
        }
      } finally {
        if (!cancelled && mountedRef.current) setLoading(false)
      }
    }

    fetch()
    return () => {
      cancelled = true
      abortController.abort()
    }
  }, [autoFetch, datasetIdRef, statusRef, severityRef])

  return { anomalies, loading, error, updateStatus, refetch }
}
