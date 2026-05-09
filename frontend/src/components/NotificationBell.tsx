import { useState, useCallback } from "react"
import { Bell, BellOff, X, CheckCircle, AlertTriangle } from "lucide-react"
import { Button } from "./ui/Button"
import { cn } from "../lib/utils"
import type { AnomalyNotification } from "../services/api"

interface NotificationBellProps {
  notifications: AnomalyNotification[]
  onMarkRead: (id: string) => Promise<void>
  onRefetch: () => Promise<void>
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "—"
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export function NotificationBell({ notifications, onMarkRead, onRefetch }: NotificationBellProps) {
  const [open, setOpen] = useState(false)
  const unread = notifications.filter((n) => !n.read)
  const unreadCount = unread.length

  const handleMarkAllRead = useCallback(async () => {
    for (const n of unread) {
      if (!n.read) await onMarkRead(n.id)
    }
    onRefetch()
  }, [unread, onMarkRead, onRefetch])

  return (
    <div className="relative">
      <Button
        variant="ghost"
        size="sm"
        className="relative"
        onClick={() => setOpen(!open)}
      >
        {unreadCount > 0 ? (
          <Bell className="h-5 w-5 text-amber-600" />
        ) : (
          <BellOff className="h-5 w-5 text-muted-foreground" />
        )}
        {unreadCount > 0 && (
          <span className="absolute -top-1 -right-1 h-4 min-w-4 px-1 flex items-center justify-center rounded-full bg-destructive text-destructive-foreground text-[10px] font-bold">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full mt-2 w-96 bg-white border rounded-lg shadow-lg z-40 max-h-96 overflow-hidden flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b">
              <h4 className="font-semibold text-sm">Notifications</h4>
              <div className="flex gap-2">
                {unreadCount > 0 && (
                  <Button variant="ghost" size="sm" onClick={handleMarkAllRead}>
                    Mark all read
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>
            <div className="overflow-y-auto flex-1">
              {notifications.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No notifications
                </p>
              ) : (
                notifications.map((n) => (
                  <div
                    key={n.id}
                    className={cn(
                      "px-4 py-3 border-b last:border-b-0 flex items-start gap-3",
                      !n.read && "bg-amber-50"
                    )}
                  >
                    <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">
                        {n.anomaly?.metric_name || "Anomaly detected"}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {n.anomaly?.severity} severity
                        {n.anomaly?.dataset_id && ` · ${n.anomaly.dataset_id.slice(0, 8)}...`}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {formatDate(n.created_at)}
                      </p>
                    </div>
                    {!n.read && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onMarkRead(n.id).then(onRefetch)}
                      >
                        <CheckCircle className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}