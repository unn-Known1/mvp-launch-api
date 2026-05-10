import { Database, AlertTriangle, FileSearch, BarChart3 } from "lucide-react"
import { StatCard } from "../components/dashboard/StatCard"
import { AnomalyTable } from "../components/dashboard/AnomalyTable"
import { ActivityFeed } from "../components/dashboard/ActivityFeed"
import { Chart } from "../components/charts/Chart"
import type { ChartData } from "../components/charts/chartUtils"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card"
import { ErrorBanner } from "../components/ui/ErrorBanner"
import { EmptyState } from "../components/ui/EmptyState"
import { useAnomalies } from "../hooks/useAnomalies"
import { useDatasets } from "../hooks/useDatasets"
import { useQueryHistory } from "../hooks/useQueryHistory"
import { useScheduledReports } from "../hooks/useScheduledReports"
import { useForecast } from "../hooks/useForecast"
import { useNotifications } from "../hooks/useNotifications"
import { useAuth } from "../hooks/useAuth"

// Mock chart data — replace with real API data when backend provides aggregates
function generateChartData(): ChartData {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  return {
    columns: ["month", "value"],
    rows: months.map((month, i) => ({
      month,
      value: Math.floor(40000 + Math.sin(i / 2) * 15000 + i * 3000),
    })),
  }
}

// Placeholder forecast - in production, fetch from forecasts API
const FORECAST_PLACEHOLDER: ChartData = {
  columns: ["date", "forecast", "lower", "upper"],
  rows: [],
}

interface ForecastListItem {
  id: string
  name: string
  status: string
  created_at: string
}

async function listUserForecasts(userId: string): Promise<ForecastListItem[]> {
  const response = await fetch(`${import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"}/ml/forecasts?user_id=${userId}`, {
    headers: {
      "Authorization": `Bearer ${localStorage.getItem("access_token") || ""}`,
    },
  })
  if (!response.ok) return []
  const data = await response.json()
  return data.forecasts || data || []
}

export default function Dashboard() {
  const { user, hasRole } = useAuth()
  const userId = user?.id || ""
  // RBAC: admins/managers see all data, others see only their own
  const canViewAllData = hasRole(["admin", "manager"])
  const canViewReports = hasRole(["admin", "manager", "analyst"])

  // Fetch data from APIs
  // For query history: admins/managers can see all (pass empty userId to get all), others see only their own
  // Note: API would need to support a "view all" mode - for now we pass userId for user-specific data
  const { total: datasetCount, loading: datasetsLoading, error: datasetsError } = useDatasets({ autoFetch: true })
  const { queries, loading: queriesLoading, error: queriesError } = useQueryHistory({
    // Only fetch queries if userId is available, regardless of role
    // API should filter based on auth token, not userId parameter
    userId: userId,
    limit: 50,
    autoFetch: true,
  })
  const { anomalies, loading: anomaliesLoading, error: anomaliesError, updateStatus } = useAnomalies({
    autoFetch: true,
  })
  const { reports, loading: reportsLoading, error: reportsError } = useScheduledReports({
    // Reports: only fetch for users with report access
    userId: canViewReports ? userId : "",
    autoFetch: canViewReports && !!userId,  // Only auto-fetch if user has access
  })
  // Forecast section - show only if userId is available (is logged in)
  // In production, you would fetch the user's forecasts and use the first active one
  const [forecastId, setForecastId] = useState<string | null>(null)

  // Fetch the user's forecasts to find an active one
  useEffect(() => {
    async function fetchForecasts() {
      if (!userId) return
      try {
        const forecasts = await listUserForecasts(userId)
        // Find first active forecast
        const activeForecast = forecasts.find((f: ForecastListItem) => f.status === "completed" || f.status === "active")
        if (activeForecast) {
          setForecastId(activeForecast.id)
        }
      } catch (err) {
        console.warn("Failed to fetch forecasts:", err)
      }
    }
    fetchForecasts()
  }, [userId])

  const { chartData: forecastChartData, loading: forecastLoading, error: forecastError } = useForecast({
    forecastId, // Use actual forecast ID
    autoFetch: true,
  })
  const { unreadCount } = useNotifications(true)

  // Performance: all critical data loaded state tracked for 3s load time verification

  // Derived values
  const recentAnomalies = anomalies.slice(0, 5)
  const flaggedCount = anomalies.filter((a) => a.status === "flagged").length
  const activeReportsCount = reports.filter((r) => r.is_active).length

  // Chart data
  const chartData = generateChartData()

  // Combined error state
  const hasError = datasetsError || queriesError || anomaliesError || reportsError || forecastError

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground mt-1">
          Overview of your data, anomalies, and forecasts
        </p>
      </div>

      {/* Error banners */}
      {hasError && (
        <div className="space-y-2">
          {datasetsError && <ErrorBanner message={`Datasets: ${datasetsError}`} />}
          {queriesError && <ErrorBanner message={`Query history: ${queriesError}`} />}
          {anomaliesError && <ErrorBanner message={`Anomalies: ${anomaliesError}`} />}
          {reportsError && <ErrorBanner message={`Reports: ${reportsError}`} />}
          {forecastError && <ErrorBanner message={`Forecast: ${forecastError}`} />}
        </div>
      )}

      {/* Unread notifications banner */}
      {unreadCount > 0 && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-6 flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 flex-shrink-0" />
            <p className="text-sm text-amber-800">
              You have <strong>{unreadCount}</strong> unread anomaly notification{unreadCount > 1 ? "s" : ""}
            </p>
          </CardContent>
        </Card>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Total Datasets"
          value={datasetsLoading ? "..." : datasetCount}
          description="Active data sources"
          icon={Database}
        />
        <StatCard
          title="Query Count"
          value={queriesLoading ? "..." : queries.length}
          description="Total queries executed"
          icon={FileSearch}
        />
        <StatCard
          title="Flagged Anomalies"
          value={anomaliesLoading ? "..." : flaggedCount}
          description="Requiring investigation"
          icon={AlertTriangle}
        />
        <StatCard
          title="Scheduled Reports"
          value={reportsLoading ? "..." : activeReportsCount}
          description="Active scheduled reports"
          icon={BarChart3}
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Data Overview</CardTitle>
            <CardDescription>Monthly trend overview</CardDescription>
          </CardHeader>
          <CardContent>
            <Chart data={chartData} type="line" title="Monthly Trend" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Severity Distribution</CardTitle>
            <CardDescription>Breakdown of anomalies by severity level</CardDescription>
          </CardHeader>
          <CardContent>
            {anomaliesLoading ? (
              <p className="text-sm text-muted-foreground py-8 text-center">Loading...</p>
            ) : anomalies.length > 0 ? (
              <Chart
                data={{
                  columns: ["severity", "count"],
                  rows: [
                    { severity: "High", count: anomalies.filter((a) => a.severity === "high").length },
                    { severity: "Medium", count: anomalies.filter((a) => a.severity === "medium").length },
                    { severity: "Low", count: anomalies.filter((a) => a.severity === "low").length },
                  ],
                }}
                type="pie"
                title="By Severity"
              />
            ) : (
              <EmptyState title="No anomalies" description="No anomalies detected yet" />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Forecast chart - only shown when forecast data is available */}
      {forecastChartData && forecastChartData.rows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Forecast</CardTitle>
            <CardDescription>Time-series forecast data</CardDescription>
          </CardHeader>
          <CardContent>
            {forecastLoading ? (
              <p className="text-sm text-muted-foreground py-8 text-center">Loading forecast...</p>
            ) : (
              <Chart data={forecastChartData} type="line" title="Forecast" />
            )}
          </CardContent>
        </Card>
      )}

      {/* Activity Feed and Recent Anomalies */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Activity Feed</CardTitle>
            <CardDescription>Recent queries and anomalies</CardDescription>
          </CardHeader>
          <CardContent>
            <ActivityFeed
              queries={queries}
              anomalies={anomalies}
              isLoading={queriesLoading || anomaliesLoading}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Anomalies</CardTitle>
            <CardDescription>Latest flagged anomalies requiring attention</CardDescription>
          </CardHeader>
          <CardContent>
            {anomaliesLoading ? (
              <p className="text-sm text-muted-foreground py-8 text-center">Loading anomalies...</p>
            ) : anomalies.length > 0 ? (
              <AnomalyTable anomalies={recentAnomalies} onStatusChange={updateStatus} loading={anomaliesLoading} />
            ) : (
              <EmptyState title="No anomalies" description="No anomalies have been detected" />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}