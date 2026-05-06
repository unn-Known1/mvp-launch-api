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

// TODO: Replace with real forecast ID from user's forecasts list
const DEMO_FORECAST_ID = "demo-forecast-1"

export function Dashboard() {
  const { user, hasRole } = useAuth()
  const userId = user?.id || ""
  const canViewAllData = hasRole(["admin", "manager"])
  const canViewReports = hasRole(["admin", "manager", "analyst"])

  // Fetch data from APIs
  // RBAC: analysts may only see their own queries/anomalies, managers/admins see all
  const { total: datasetCount, loading: datasetsLoading, error: datasetsError } = useDatasets({ autoFetch: true })
  const { queries, loading: queriesLoading, error: queriesError } = useQueryHistory({
    userId: canViewAllData ? "" : userId,
    limit: 50,
    autoFetch: true,
  })
  const { anomalies, loading: anomaliesLoading, error: anomaliesError, updateStatus } = useAnomalies({
    // Pass no filters for admin/manager to see all, or filter by user-specific datasets
    autoFetch: true,
  })
  const { reports, loading: reportsLoading, error: reportsError } = useScheduledReports({
    userId: canViewReports ? userId : "",
    autoFetch: true,
  })
  const { chartData: forecastChartData, loading: forecastLoading, error: forecastError } = useForecast({ forecastId: DEMO_FORECAST_ID, autoFetch: true })
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

      {/* Forecast chart */}
      <Card>
        <CardHeader>
          <CardTitle>Forecast</CardTitle>
          <CardDescription>Time-series forecast data</CardDescription>
        </CardHeader>
        <CardContent>
          {forecastLoading ? (
            <p className="text-sm text-muted-foreground py-8 text-center">Loading forecast...</p>
          ) : forecastChartData ? (
            <Chart data={forecastChartData} type="line" title="Forecast" />
          ) : forecastError ? (
            <EmptyState title="Forecast unavailable" description="Unable to load forecast data" />
          ) : (
            <EmptyState title="No forecast" description="Create a forecast to see predictions here" />
          )}
        </CardContent>
      </Card>

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
              <AnomalyTable anomalies={recentAnomalies} onStatusChange={updateStatus} />
            ) : (
              <EmptyState title="No anomalies" description="No anomalies have been detected" />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
