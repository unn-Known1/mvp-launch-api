import { useState, useEffect, useMemo, useCallback } from "react"
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  Search,
  Filter,
  Eye,
  X,
  Bell,
  BellOff,
  Scan,
  ArrowUpDown,
  ChevronDown,
  ChevronUp,
  TableProperties,
} from "lucide-react"
import { Button } from "../components/ui/Button"
import { Input } from "../components/ui/Input"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card"
import { ErrorBanner } from "../components/ui/ErrorBanner"
import { EmptyState } from "../components/ui/EmptyState"
import { cn } from "../lib/utils"
import { useAnomalies } from "../hooks/useAnomalies"
import { useDatasets } from "../hooks/useDatasets"
import {
  listThresholds,
  scanAnomalies,
  markNotificationRead,
  getAnomalyNotifications,
  updateAnomaly,
  type Anomaly,
  type AnomalyThreshold,
  type AnomalyNotification,
} from "../services/api"

const severityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 }

const severityColors: Record<string, string> = {
  low: "bg-blue-100 text-blue-800",
  medium: "bg-amber-100 text-amber-800",
  high: "bg-red-100 text-red-800",
}

const statusIcons: Record<string, typeof AlertTriangle> = {
  flagged: AlertTriangle,
  investigated: CheckCircle,
  dismissed: XCircle,
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

function formatValue(value: string | null): string {
  if (value === null || value === undefined) return "—"
  const num = parseFloat(value)
  if (isNaN(num)) return value
  return num.toLocaleString(undefined, { maximumFractionDigits: 4 })
}

// ── Notification Bell ───────────────────────────────────────────────────────────

interface NotificationBellProps {
  notifications: AnomalyNotification[]
  onMarkRead: (id: string) => Promise<void>
  onRefetch: () => Promise<void>
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

// ── Threshold Table ────────────────────────────────────────────────────────────

interface ThresholdTableProps {
  thresholds: AnomalyThreshold[]
  datasets: { id: string; name: string }[]
}

function ThresholdTable({ thresholds, datasets }: ThresholdTableProps) {
  const [open, setOpen] = useState(false)
  const datasetNameMap = useMemo(() => {
    const m: Record<string, string> = {}
    datasets.forEach((d) => { m[d.id] = d.name })
    return m
  }, [datasets])

  if (thresholds.length === 0) return null

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TableProperties className="h-5 w-5 text-muted-foreground" />
            <div>
              <CardTitle className="text-base">Detection Thresholds</CardTitle>
              <CardDescription>Read-only view of current anomaly detection settings</CardDescription>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setOpen(!open)}>
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </Button>
        </div>
      </CardHeader>
      {open && (
        <CardContent>
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="px-4 py-2 text-left font-medium">Dataset</th>
                  <th className="px-4 py-2 text-left font-medium">Metric</th>
                  <th className="px-4 py-2 text-left font-medium">Z-Score Threshold</th>
                  <th className="px-4 py-2 text-left font-medium">IQR Multiplier</th>
                  <th className="px-4 py-2 text-left font-medium">Enabled</th>
                </tr>
              </thead>
              <tbody>
                {thresholds.map((t) => (
                  <tr key={t.id} className="border-b last:border-b-0">
                    <td className="px-4 py-2 font-medium">
                      {datasetNameMap[t.dataset_id] || t.dataset_id.slice(0, 8) + "..."}
                    </td>
                    <td className="px-4 py-2">{t.metric_name}</td>
                    <td className="px-4 py-2 font-mono text-xs">{t.z_score_threshold}</td>
                    <td className="px-4 py-2 font-mono text-xs">{t.iqr_multiplier}</td>
                    <td className="px-4 py-2">
                      <span className={cn("inline-flex px-2 py-0.5 rounded-full text-xs font-medium",
                        t.enabled ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-600"
                      )}>
                        {t.enabled ? "Yes" : "No"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      )}
    </Card>
  )
}

// ── Detail Panel ───────────────────────────────────────────────────────────────

interface DetailPanelProps {
  anomaly: Anomaly
  datasetName: string
  onClose: () => void
  onStatusChange: (id: string, status: "investigated" | "dismissed", notes?: string) => Promise<void>
}

function DetailPanel({ anomaly, datasetName, onClose, onStatusChange }: DetailPanelProps) {
  const [notes, setNotes] = useState(anomaly.notes || "")
  const [updating, setUpdating] = useState(false)

  const handleStatusUpdate = async (status: "investigated" | "dismissed") => {
    setUpdating(true)
    try {
      await onStatusChange(anomaly.id, status, notes || undefined)
      onClose()
    } catch {
      // error handled by parent
    } finally {
      setUpdating(false)
    }
  }

  const StatusIcon = statusIcons[anomaly.status] || AlertTriangle

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">Anomaly Detail</h3>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="px-6 py-4 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-xs text-muted-foreground">Severity</p>
              <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium mt-1", severityColors[anomaly.severity])}>
                {anomaly.severity}
              </span>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Status</p>
              <span className="inline-flex items-center gap-1.5 text-xs mt-1">
                <StatusIcon className="h-3.5 w-3.5" />
                {anomaly.status}
              </span>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Metric</p>
              <p className="font-medium text-sm mt-1">{anomaly.metric_name}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Dataset</p>
              <p className="text-sm mt-1">{datasetName}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Timestamp</p>
              <p className="text-sm mt-1">{formatDate(anomaly.timestamp)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Detection Method</p>
              <p className="text-sm mt-1 capitalize">{anomaly.detection_method}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 pt-2 border-t">
            <div>
              <p className="text-xs text-muted-foreground">Expected Value</p>
              <p className="font-mono text-sm mt-1">{formatValue(anomaly.expected_value)}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground">Actual Value</p>
              <p className="font-mono text-sm font-medium text-red-600 mt-1">{formatValue(anomaly.actual_value)}</p>
            </div>
          </div>

          {(anomaly.z_score || anomaly.iqr_lower) && (
            <div className="grid grid-cols-3 gap-4 pt-2 border-t">
              {anomaly.z_score && (
                <div>
                  <p className="text-xs text-muted-foreground">Z-Score</p>
                  <p className="font-mono text-sm mt-1">{formatValue(anomaly.z_score)}</p>
                </div>
              )}
              {anomaly.iqr_lower && (
                <div>
                  <p className="text-xs text-muted-foreground">IQR Lower</p>
                  <p className="font-mono text-sm mt-1">{formatValue(anomaly.iqr_lower)}</p>
                </div>
              )}
              {anomaly.iqr_upper && (
                <div>
                  <p className="text-xs text-muted-foreground">IQR Upper</p>
                  <p className="font-mono text-sm mt-1">{formatValue(anomaly.iqr_upper)}</p>
                </div>
              )}
            </div>
          )}

          {anomaly.confidence !== null && anomaly.confidence !== undefined && (
            <div className="pt-2 border-t">
              <p className="text-xs text-muted-foreground">Confidence</p>
              <p className="text-sm mt-1">{(anomaly.confidence * 100).toFixed(1)}%</p>
            </div>
          )}

          <div className="pt-2 border-t">
            <label className="text-xs text-muted-foreground">Notes</label>
            <textarea
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring min-h-[80px]"
              placeholder="Add investigation notes..."
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </div>

        {anomaly.status === "flagged" && (
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t">
            <Button
              variant="outline"
              onClick={() => handleStatusUpdate("dismissed")}
              disabled={updating}
            >
              Dismiss
            </Button>
            <Button
              onClick={() => handleStatusUpdate("investigated")}
              disabled={updating}
            >
              Mark Investigated
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main Page ──────────────────────────────────────────────────────────────────

export function AnomaliesPage() {
  const {
    anomalies,
    loading,
    error,
    refetch: refetchAnomalies,
  } = useAnomalies({ autoFetch: true })

  const { datasets } = useDatasets({ autoFetch: true })

  const [search, setSearch] = useState("")
  const [filterSeverity, setFilterSeverity] = useState<string>("")
  const [filterStatus, setFilterStatus] = useState<string>("")
  const [filterDataset, setFilterDataset] = useState<string>("")
  const [sortDesc, setSortDesc] = useState(true)
  const [selectedAnomaly, setSelectedAnomaly] = useState<Anomaly | null>(null)
  const [scanLoading, setScanLoading] = useState(false)
  const [scanResult, setScanResult] = useState<string | null>(null)
  const [thresholds, setThresholds] = useState<AnomalyThreshold[]>([])
  const [notifications, setNotifications] = useState<AnomalyNotification[]>([])

  const datasetNames = useMemo(() => datasets.reduce<Record<string, string>>((acc, d) => { acc[d.id] = d.name; return acc }, {}), [datasets])

  // Fetch thresholds, notifications on mount
  const loadExtras = useCallback(async () => {
    try {
      const [thresh, notifs] = await Promise.all([
        listThresholds(),
        getAnomalyNotifications(false),
      ])
      setThresholds(thresh)
      setNotifications(notifs)
    } catch {
      // non-blocking
    }
  }, [])

  // Initial load of extras
  useEffect(() => { loadExtras() }, [loadExtras])

  const filteredAnomalies = useMemo(() => {
    let result = [...anomalies]

    // Filter by search text (metric name)
    if (search) {
      const q = search.toLowerCase()
      result = result.filter(
        (a) =>
          a.metric_name.toLowerCase().includes(q) ||
          (datasetNames[a.dataset_id] || "").toLowerCase().includes(q)
      )
    }

    // Filter by dataset
    if (filterDataset) {
      result = result.filter((a) => a.dataset_id === filterDataset)
    }

    // Filter by severity
    if (filterSeverity) {
      result = result.filter((a) => a.severity === filterSeverity)
    }

    // Filter by status
    if (filterStatus) {
      result = result.filter((a) => a.status === filterStatus)
    }

    // Sort: severity first (high > medium > low), then timestamp
    result.sort((a, b) => {
      const sevDiff = severityOrder[a.severity] - severityOrder[b.severity]
      if (sevDiff !== 0) return sortDesc ? sevDiff : -sevDiff
      const tsA = new Date(a.timestamp).getTime()
      const tsB = new Date(b.timestamp).getTime()
      return sortDesc ? tsB - tsA : tsA - tsB
    })

    return result
  }, [anomalies, search, filterDataset, filterSeverity, filterStatus, sortDesc])

  const handleScan = async () => {
    setScanLoading(true)
    setScanResult(null)
    try {
      const result = await scanAnomalies()
      setScanResult(
        `Scan complete: ${result.total_anomalies_found} anomal${result.total_anomalies_found === 1 ? "y" : "ies"} found across ${result.scanned_datasets} dataset${result.scanned_datasets !== 1 ? "s" : ""}`
      )
      refetchAnomalies()
    } catch (err) {
      setScanResult(`Scan failed: ${err instanceof Error ? err.message : "Unknown error"}`)
    } finally {
      setScanLoading(false)
    }
  }

  const handleMarkNotificationRead = async (notificationId: string) => {
    await markNotificationRead(notificationId)
    const updated = notifications.map((n) => n.id === notificationId ? { ...n, read: true } : n)
    setNotifications(updated)
  }

  const handleRefetchNotifications = async () => {
    try {
      const data = await getAnomalyNotifications(false)
      setNotifications(data)
    } catch {
      // non-blocking
    }
  }

  const handleStatusChange = async (
    anomalyId: string,
    status: "investigated" | "dismissed",
    notes?: string
  ) => {
    await updateAnomaly(anomalyId, { status, notes })
    refetchAnomalies()
  }

  const clearFilters = () => {
    setSearch("")
    setFilterSeverity("")
    setFilterStatus("")
    setFilterDataset("")
  }

  const hasActiveFilters = search || filterSeverity || filterStatus || filterDataset

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Anomaly Detection</h1>
          <p className="text-muted-foreground mt-1">
            Monitor and investigate detected anomalies
          </p>
        </div>
        <div className="flex items-center gap-3">
          <NotificationBell
            notifications={notifications}
            onMarkRead={handleMarkNotificationRead}
            onRefetch={handleRefetchNotifications}
          />
          <Button onClick={handleScan} disabled={scanLoading}>
            <Scan className="mr-2 h-4 w-4" />
            {scanLoading ? "Scanning..." : "Scan"}
          </Button>
        </div>
      </div>

      {error && <ErrorBanner message={error} />}
      {scanResult && (
        <div className={cn("p-3 rounded-md text-sm", scanResult.includes("failed") ? "bg-red-50 text-red-700 border border-red-200" : "bg-green-50 text-green-700 border border-green-200")}>
          {scanResult}
        </div>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <CardTitle className="text-base">Filters</CardTitle>
              {hasActiveFilters && (
                <Button variant="ghost" size="sm" onClick={clearFilters}>
                  Clear
                </Button>
              )}
            </div>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search metric or dataset..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {/* Dataset filter */}
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={filterDataset}
              onChange={(e) => setFilterDataset(e.target.value)}
            >
              <option value="">All Datasets</option>
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>

            {/* Severity filter */}
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={filterSeverity}
              onChange={(e) => setFilterSeverity(e.target.value)}
            >
              <option value="">All Severities</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            {/* Status filter */}
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="">All Statuses</option>
              <option value="flagged">Flagged</option>
              <option value="investigated">Investigated</option>
              <option value="dismissed">Dismissed</option>
            </select>

            {/* Sort direction */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSortDesc(!sortDesc)}
            >
              <ArrowUpDown className="mr-2 h-3.5 w-3.5" />
              {sortDesc ? "Newest First" : "Oldest First"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Threshold Table */}
      <ThresholdTable thresholds={thresholds} datasets={datasets} />

      {/* Anomalies Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            Anomalies
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              {filteredAnomalies.length} result{filteredAnomalies.length !== 1 ? "s" : ""}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-12 bg-muted/50 rounded animate-pulse" />
              ))}
            </div>
          ) : filteredAnomalies.length === 0 ? (
            <EmptyState
              icon={<AlertTriangle className="h-12 w-12" />}
              title={hasActiveFilters ? "No matching anomalies" : "No anomalies detected"}
              description={hasActiveFilters ? "Try adjusting your filters" : "Run a scan to detect anomalies in your datasets"}
              action={
                !hasActiveFilters ? (
                  <Button onClick={handleScan} disabled={scanLoading}>
                    <Scan className="mr-2 h-4 w-4" />
                    Scan for Anomalies
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="rounded-md border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium">Severity</th>
                    <th className="px-4 py-3 text-left font-medium">Metric</th>
                    <th className="px-4 py-3 text-left font-medium">Dataset</th>
                    <th className="px-4 py-3 text-left font-medium">Expected</th>
                    <th className="px-4 py-3 text-left font-medium">Actual</th>
                    <th className="px-4 py-3 text-left font-medium">Status</th>
                    <th className="px-4 py-3 text-left font-medium">Timestamp</th>
                    <th className="px-4 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredAnomalies.map((anomaly) => {
                    const StatusIcon = statusIcons[anomaly.status] || AlertTriangle
                    return (
                      <tr key={anomaly.id} className="border-b last:border-b-0 hover:bg-muted/30">
                        <td className="px-4 py-3">
                          <span className={cn("inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium", severityColors[anomaly.severity])}>
                            {anomaly.severity}
                          </span>
                        </td>
                        <td className="px-4 py-3 font-medium">{anomaly.metric_name}</td>
                        <td className="px-4 py-3 text-muted-foreground text-xs">
                          {datasetNames[anomaly.dataset_id] || anomaly.dataset_id.slice(0, 8) + "..."}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground font-mono text-xs">
                          {formatValue(anomaly.expected_value)}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-red-600">
                          {formatValue(anomaly.actual_value)}
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <StatusIcon className="h-3.5 w-3.5" />
                            {anomaly.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground text-xs">
                          {formatDate(anomaly.timestamp)}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => setSelectedAnomaly(anomaly)}
                            >
                              <Eye className="h-3.5 w-3.5" />
                            </Button>
                            {anomaly.status === "flagged" && (
                              <>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleStatusChange(anomaly.id, "investigated")}
                                >
                                  <CheckCircle className="h-3.5 w-3.5 text-green-600" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleStatusChange(anomaly.id, "dismissed")}
                                >
                                  <XCircle className="h-3.5 w-3.5 text-red-600" />
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Detail Panel */}
      {selectedAnomaly && (
        <DetailPanel
          anomaly={selectedAnomaly}
          datasetName={datasetNames[selectedAnomaly.dataset_id] || selectedAnomaly.dataset_id.slice(0, 8) + "..."}
          onClose={() => setSelectedAnomaly(null)}
          onStatusChange={handleStatusChange}
        />
      )}
    </div>
  )
}
