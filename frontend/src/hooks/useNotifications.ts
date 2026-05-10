import { useState, useEffect, useCallback } from "react"
import { getAnomalyNotifications, markNotificationRead, type AnomalyNotification } from "../services/api"

interface UseNotificationsResult {
  notifications: AnomalyNotification[]
  unreadCount: number
  loading: boolean
  error: string | null
  markRead: (notificationId: string) => Promise<void>
  refetch: () => Promise<void>
}

export function useNotifications(unreadOnly = false): UseNotificationsResult {
  const [notifications, setNotifications] = useState<AnomalyNotification[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getAnomalyNotifications(unreadOnly)
      setNotifications(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch notifications")
    } finally {
      setLoading(false)
    }
  }, [unreadOnly])

  const markRead = useCallback(async (notificationId: string) => {
    try {
      await markNotificationRead(notificationId)
      setNotifications((prev) =>
        prev.map((n) => (n.id === notificationId ? { ...n, read: true } : n))
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to mark notification as read")
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function fetch() {
      setLoading(true)
      setError(null)
      try {
        const data = await getAnomalyNotifications(unreadOnly)
        if (!cancelled) setNotifications(data)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to fetch notifications")
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetch()
    return () => {
      cancelled = true
    }
  }, [unreadOnly])

  const unreadCount = notifications.filter((n) => !n.read).length

  return { notifications, unreadCount, loading, error, markRead, refetch }
}
