import { useState, useEffect } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card"
import { useAuth } from "../hooks/useAuth"
import { TrendingUp } from "lucide-react"

interface Forecast {
  id: string
  name: string
  dataset_id: string
  target_column: string
  periods: number
  status: string
  created_at: string
}

async function listForecasts(userId: string): Promise<Forecast[]> {
  const response = await fetch(
    `${import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"}/ml/forecasts?user_id=${userId}`,
    {
      headers: {
        "Authorization": `Bearer ${localStorage.getItem("access_token") || ""}`,
      },
    }
  )
  if (!response.ok) return []
  const data = await response.json()
  return data.forecasts || data || []
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—"
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  })
}

export default function ForecastsPage() {
  const { user } = useAuth()
  const [forecasts, setForecasts] = useState<Forecast[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    async function fetchForecasts() {
      if (!user?.id) return
      try {
        const data = await listForecasts(user.id)
        setForecasts(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to fetch forecasts")
      } finally {
        setLoading(false)
      }
    }
    fetchForecasts()
  }, [user?.id])

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Forecasts</h1>
        <p className="text-muted-foreground mt-1">
          View and manage your ML forecasting models
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
            <p className="text-muted-foreground text-center py-8">Loading forecasts...</p>
          </CardContent>
        </Card>
      ) : forecasts.length === 0 ? (
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center py-12">
              <TrendingUp className="h-12 w-12 text-muted-foreground mb-4" />
              <h3 className="text-lg font-medium mb-2">No forecasts yet</h3>
              <p className="text-muted-foreground">
                Create your first forecast from a dataset to see predictions here.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4">
          {forecasts.map((forecast) => (
            <Card key={forecast.id}>
              <CardHeader>
                <CardTitle>{forecast.name}</CardTitle>
                <CardDescription>
                  Target: {forecast.target_column} · {forecast.periods} periods
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    Dataset: {forecast.dataset_id.slice(0, 8)}...
                  </span>
                  <span className="text-muted-foreground">
                    Created: {formatDate(forecast.created_at)}
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