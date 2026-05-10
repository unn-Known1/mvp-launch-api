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

  // Track mount state to avoid setState on unmounted components
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  const refetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const filters: { dataset_id?: string; status?: string; severity?: string } = {}
      if (datasetId) filters.dataset_id = datasetId
      if (status) filters.status = status
      if (severity) filters.severity = severity
      const data = await listAnomalies(filters)
      if (mountedRef.current) setAnomalies(data)
    } catch (err) {
      if (mountedRef.current) setError(err instanceof Error ? err.message : "Failed to fetch anomalies")
    } finally {
      if (mountedRef.current) setLoading(false)
    }
  }, [datasetId, status, severity])

  const updateStatus = useCallback(
    async (anomalyId: string, newStatus: "investigated" | "dismissed", notes?: string) => {
      try {
        const updated = await updateAnomaly(anomalyId, { status: newStatus, notes })
        setAnomalies((prev) =>
          prev.map((a) => (a.id === anomalyId ? updated : a))
        )
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to update anomaly")
      }
    },
    []
  )

  // Effect to trigger initial fetch when autoFetch or filter params change
  useEffect(() => {
    if (!autoFetch) return
    let cancelled = false

    async function fetch() {
      setLoading(true)
      setError(null)
      try {
        const filters: { dataset_id?: string; status?: string; severity?: string } = {}
        if (datasetId) filters.dataset_id = datasetId
        if (status) filters.status = status
        if (severity) filters.severity = severity
        const data = await listAnomalies(filters)
        if (!cancelled) setAnomalies(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to fetch anomalies")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => {
      cancelled = true
    }
  }, [autoFetch, datasetId, status, severity])

  return { anomalies, loading, error, updateStatus, refetch }
}
