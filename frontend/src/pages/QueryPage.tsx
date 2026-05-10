import { useState, useEffect } from "react"
import { QueryResultDisplay } from "../components/charts/QueryResultDisplay"
import { Button } from "../components/ui/Button"
import { Card, CardContent } from "../components/ui/Card"
import { Input } from "../components/ui/Input"
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "../components/ui/Select"
import { submitNLQuery, listCsvDatasets, type Dataset } from "../services/api"
import type { NLQueryResult } from "../services/api"
import { useAuth } from "../hooks/useAuth"

const SAMPLE_QUERIES = [
  "Show me sales by month for 2024",
  "What are the top 10 products by revenue?",
  "Compare revenue between Q1 and Q2",
  "Show anomaly trends over time",
]

export default function QueryPage() {
  const { user } = useAuth()
  const [query, setQuery] = useState("")
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<NLQueryResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [datasets, setDatasets] = useState<Dataset[]>([])
  const [selectedDataSourceId, setSelectedDataSourceId] = useState<string>("")

  // Fetch available data sources on mount
  useEffect(() => {
    async function fetchDatasets() {
      try {
        const data = await listCsvDatasets()
        setDatasets(data)
        if (data.length > 0) {
          setSelectedDataSourceId(data[0].id)
        }
      } catch {
        // Use empty string if fetch fails
      }
    }
    fetchDatasets()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!query.trim() || !selectedDataSourceId) return

    setLoading(true)
    setError(null)

    try {
      const res = await submitNLQuery({
        query,
        data_source_id: selectedDataSourceId,
        user_id: user?.id || "",
        execute: true,
      })
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to execute query")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">Query Data</h1>
        <p className="text-muted-foreground">
          Ask questions in natural language and get visualized results
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex gap-2">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="e.g., Show me sales by month for 2024"
                className="flex-1"
              />
              <Select value={selectedDataSourceId} onValueChange={setSelectedDataSourceId}>
                <SelectTrigger className="w-48">
                  <SelectValue placeholder="Select data source" />
                </SelectTrigger>
                <SelectContent>
                  {datasets.length === 0 && <SelectItem value="none">No datasets available</SelectItem>}
                  {datasets.map((ds) => (
                    <SelectItem key={ds.id} value={ds.id}>
                      {ds.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button type="submit" disabled={loading || !selectedDataSourceId}>
                {loading ? "Running..." : "Query"}
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="text-sm text-muted-foreground">Try:</span>
              {SAMPLE_QUERIES.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="text-sm px-3 py-1 rounded-full border hover:bg-accent"
                  onClick={() => setQuery(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card>
          <CardContent className="pt-6 text-destructive">
            {error}
          </CardContent>
        </Card>
      )}

      {result && <QueryResultDisplay result={result} />}
    </div>
  )
}
