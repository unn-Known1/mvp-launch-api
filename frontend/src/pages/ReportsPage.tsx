import { useState, useEffect } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card"
import { useAuth } from "../hooks/useAuth"
import { FileText } from "lucide-react"
import { listScheduledReports, type ScheduledReport } from "../services/api"

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—"
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

function getStatusBadgeClass(isActive: boolean): string {
  return isActive ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-700"
}

export default function ReportsPage() {
  const { user } = useAuth()
  const [reports, setReports] = useState<ScheduledReport[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchReports() {
      if (!user?.id) return
      try {
        const data = await listScheduledReports(user.id)
        setReports(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch reports")
      } finally {
        setLoading(false)
      }
    }
    fetchReports()
  }, [user?.id])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Reports</h1>
        <p className="text-muted-foreground mt-1">
          View and manage your scheduled reports
        </p>
      </div>

      {error && (
        <Card className="border-destructive">
          <CardContent className="pt-6 text-destructive">{error}</CardContent>
        </Card>
      )}

      {loading ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground text-center py-8">Loading reports...</p>
          </CardContent>
        </Card>
      ) : reports.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center py-12">
              <FileText className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No reports yet</h3>
              <p className="text-muted-foreground">
                Create your first scheduled report to see it here.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {reports.map((report) => (
            <Card key={report.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{report.name}</CardTitle>
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusBadgeClass(report.is_active)}`}>
                    {report.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
                {report.description && <CardDescription>{report.description}</CardDescription>}
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    Frequency: {report.frequency}
                  </span>
                  <span className="text-muted-foreground">
                    Next run: {formatDate(report.next_run_at)}
                  </span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}