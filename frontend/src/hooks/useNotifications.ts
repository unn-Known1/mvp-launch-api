import { useState, useEffect, useCallback, useRef } from "react"
import { getAnomalyNotifications, markNotificationRead, type AnomalyNotification } from "../services/api"

interface UseNotificationsResult {
  notifications: AnomalyNotification[]
  unreadCount: number
  loading: boolean
  error: string | null
  markRead: (notificationId: string) => Promise<void>
  refetch: () => Promise<void>
}

function createError(message: string, cause?: Error): Error {
  const err = new Error(message)
  if (cause) err.cause = cause
  return err
}

export function useNotifications(unreadOnly = false): UseNotificationsResult {
  const [notifications, setNotifications] = useState<AnomalyNotification[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const unreadOnlyRef = useRef(unreadOnly)

  // Keep refs fresh
  useEffect(() => {
    unreadOnlyRef.current = unreadOnly
  }, [unreadOnly])

  const refetch = useCallback(async () => {
    // Cancel any in-flight request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()
    setLoading(true)
    setError(null)
    try {
      const data = await getAnomalyNotifications(unreadOnlyRef.current, abortControllerRef.current.signal)
      setNotifications(data)
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        return
      }
      const errorMessage = err instanceof Error ? err.message : "Failed to fetch notifications"
      setError(errorMessage)
      throw createError(errorMessage, err instanceof Error ? err : undefined)
    } finally {
      setLoading(false)
    }
  }, []) // No deps - uses refs

  const markRead = useCallback(async (notificationId: string) => {
    try {
      await markNotificationRead(notificationId)
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n))
      )
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Failed to mark notification as read"
      setError(errorMessage)
      throw createError(errorMessage, err instanceof Error ? err : undefined)
    }
  }, [])

  useEffect(() => {
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
        const data = await getAnomalyNotifications(unreadOnlyRef.current, abortController.signal)
        if (!cancelled) setNotifications(data)
      } catch (err) {
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        const errorMessage = err instanceof Error ? err.message : "Failed to fetch notifications"
        if (!cancelled) {
          setError(errorMessage)
          console.error("[useNotifications] Fetch error:", err)
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
  }, [unreadOnlyRef]) // Use ref, not value

  const unreadCount = notifications.filter((n) => !n.read).length

  return { notifications, unreadCount, loading, error, markRead, refetch }
}
