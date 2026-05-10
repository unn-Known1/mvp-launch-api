import { useEffect, useRef, useCallback, useState } from "react"
import { getToken } from "../services/api"

interface AnomalyEvent {
  type: "anomaly_detected"
  timestamp: string
  anomaly: {
    id: string
    dataset_id: string
    metric_name: string
    timestamp: string | null
    expected_value: string | null
    actual_value: string
    severity: "low" | "medium" | "high"
    detection_method: string
    status: string
    created_at: string | null
  }
}

interface UseAnomalyWebSocketOptions {
  onAnomaly?: (anomaly: AnomalyEvent["anomaly"]) => void
  enabled?: boolean
}

interface UseAnomalyWebSocketResult {
  connected: boolean
  error: string | null
}

export function useAnomalyWebSocket({
  onAnomaly,
  enabled = true,
}: UseAnomalyWebSocketOptions = {}): UseAnomalyWebSocketResult {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const onAnomalyRef = useRef(onAnomaly)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Keep ref fresh
  useEffect(() => {
    onAnomalyRef.current = onAnomaly
  }, [onAnomaly])

  const MAX_RECONNECT_DELAY = 30000
  const BASE_RECONNECT_DELAY = 1000

  const connect = useCallback(async () => {
    if (!enabled || wsRef.current) return

    try {
      const token = await getToken()
      if (!token) {
        setError("No authentication token available")
        return
      }

      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:"
      const host = import.meta.env.VITE_API_URL
        ? new URL(import.meta.env.VITE_API_URL).host
        : window.location.host
      const wsUrl = `${protocol}//${host}/api/v1/anomalies/ws/anomalies?token=${token}`

      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === "anomaly_detected" && data.anomaly) {
            onAnomalyRef.current?.(data.anomaly)
          }
        } catch {
          // Ignore malformed messages
        }
      }

      ws.onclose = (event) => {
        wsRef.current = null
        setConnected(false)

        // Don't reconnect on intentional close (code 1000) or auth failure (4001)
        if (event.code === 1000 || event.code === 4001) {
          if (event.code === 4001) {
            setError("Authentication failed")
          }
          return
        }

        // Exponential backoff reconnect
        const delay = Math.min(
          BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
          MAX_RECONNECT_DELAY
        )
        reconnectAttemptsRef.current += 1

        reconnectTimeoutRef.current = setTimeout(() => {
          reconnectTimeoutRef.current = null
          connect()
        }, delay)
      }

      ws.onerror = () => {
        setError("WebSocket connection error")
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect")
    }
  }, [enabled])

  // Connect on mount / enabled change
  useEffect(() => {
    if (enabled) {
      connect()
    }

    return () => {
      // Cleanup on unmount or disabled
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
        reconnectTimeoutRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close(1000, "Component unmounted")
        wsRef.current = null
      }
    }
  }, [enabled, connect])

  return { connected, error }
}
