import { cn } from "../../lib/utils"
import { AlertTriangle, CheckCircle, XCircle } from "lucide-react"
import type { Anomaly } from "../../services/api"
import { Button } from "../ui/Button"

interface AnomalyTableProps {
  anomalies: Anomaly[]
  onStatusChange?: (anomalyId: string, status: "investigated" | "dismissed") => void
  loading?: boolean
  className?: string
}

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

export function AnomalyTable({ anomalies, onStatusChange, loading = false, className }: AnomalyTableProps) {
  if (loading) {
    return (
      <div className={cn("rounded-lg border bg-card p-8", className)}>
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-10 bg-muted/50 rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (anomalies.length === 0) {
    return (
      <div className={cn("rounded-lg border bg-card p-8 text-center text-muted-foreground", className)}>
        No anomalies detected
      </div>
    )
  }

  return (
    <div className={cn("rounded-md border overflow-hidden", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="px-4 py-3 text-left font-medium">Severity</th>
            <th className="px-4 py-3 text-left font-medium">Metric</th>
            <th className="px-4 py-3 text-left font-medium">Expected</th>
            <th className="px-4 py-3 text-left font-medium">Actual</th>
            <th className="px-4 py-3 text-left font-medium">Status</th>
            <th className="px-4 py-3 text-left font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {anomalies.map((anomaly) => {
            const StatusIcon = statusIcons[anomaly.status] || AlertTriangle
            return (
              <tr key={anomaly.id} className="border-b last:border-b-0">
                <td className="px-4 py-3">
                  <span
                    className={cn(
                      "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium",
                      severityColors[anomaly.severity]
                    )}
                  >
                    {anomaly.severity}
                  </span>
                </td>
                <td className="px-4 py-3 font-medium">{anomaly.metric_name}</td>
                <td className="px-4 py-3 text-muted-foreground">
                  {anomaly.expected_value ?? "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs">{anomaly.actual_value}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1.5 text-xs">
                    <StatusIcon className="h-3.5 w-3.5" />
                    {anomaly.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {anomaly.status === "flagged" && onStatusChange && (
                    <div className="flex gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onStatusChange(anomaly.id, "investigated")}
                      >
                        Investigate
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onStatusChange(anomaly.id, "dismissed")}
                      >
                        Dismiss
                      </Button>
                    </div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
