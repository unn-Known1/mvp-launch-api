import { Clock, AlertTriangle, CheckCircle } from "lucide-react"
import type { NLQueryResult } from "../../services/api"
import type { Anomaly } from "../../services/api"
import { cn } from "../../lib/utils"

interface ActivityFeedProps {
  queries: NLQueryResult[]
  anomalies: Anomaly[]
  isLoading?: boolean
}

function formatTimeAgo(dateString: string): string {
  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return "just now"
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  return `${diffDays}d ago`
}

function QueryItem({ query }: { query: NLQueryResult }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b last:border-0">
      <div className="mt-0.5">
        <CheckCircle className="h-4 w-4 text-emerald-500" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{query.natural_language_query}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-muted-foreground">{formatTimeAgo(query.created_at)}</span>
          <span className={cn(
            "text-xs px-1.5 py-0.5 rounded",
            query.confidence_level === "high" ? "bg-emerald-100 text-emerald-700" :
            query.confidence_level === "medium" ? "bg-amber-100 text-amber-700" :
            "bg-red-100 text-red-700"
          )}>
            {query.confidence_level}
          </span>
        </div>
      </div>
    </div>
  )
}

function AnomalyItem({ anomaly }: { anomaly: Anomaly }) {
  return (
    <div className="flex items-start gap-3 py-3 border-b last:border-0">
      <div className="mt-0.5">
        <AlertTriangle className={cn(
          "h-4 w-4",
          anomaly.severity === "high" ? "text-red-500" :
          anomaly.severity === "medium" ? "text-amber-500" :
          "text-blue-500"
        )} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{anomaly.metric_name}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-xs text-muted-foreground">{formatTimeAgo(anomaly.created_at)}</span>
          <span className={cn(
            "text-xs px-1.5 py-0.5 rounded capitalize",
            anomaly.status === "flagged" ? "bg-red-100 text-red-700" :
            anomaly.status === "investigated" ? "bg-blue-100 text-blue-700" :
            "bg-gray-100 text-gray-700"
          )}>
            {anomaly.status}
          </span>
        </div>
      </div>
    </div>
  )
}

export function ActivityFeed({ queries, anomalies, isLoading }: ActivityFeedProps) {
  if (isLoading) {
    return (
      <div className="space-y-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="animate-pulse flex items-start gap-3 py-3">
            <div className="h-4 w-4 bg-muted rounded-full mt-0.5" />
            <div className="flex-1 space-y-2">
              <div className="h-4 bg-muted rounded w-3/4" />
              <div className="h-3 bg-muted rounded w-1/4" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  const sortedQueries = [...queries]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)

  const sortedAnomalies = [...anomalies]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)

  if (sortedQueries.length === 0 && sortedAnomalies.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-8 text-center">
        No recent activity
      </p>
    )
  }

  return (
    <div className="space-y-4">
      {sortedQueries.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Clock className="h-3.5 w-3.5" />
            Recent Queries
          </h4>
          {sortedQueries.map((query) => (
            <QueryItem key={query.id} query={query} />
          ))}
        </div>
      )}

      {sortedAnomalies.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <AlertTriangle className="h-3.5 w-3.5" />
            Recent Anomalies
          </h4>
          {sortedAnomalies.map((anomaly) => (
            <AnomalyItem key={anomaly.id} anomaly={anomaly} />
          ))}
        </div>
      )}
    </div>
  )
}
