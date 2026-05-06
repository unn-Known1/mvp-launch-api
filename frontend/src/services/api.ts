const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"

export interface NLQueryRequest {
  query: string
  data_source_id: string
  user_id: string
  execute?: boolean
  max_rows?: number
}

export interface NLQueryResult {
  id: string
  natural_language_query: string
  generated_sql: string
  executed_sql: string
  results: Record<string, unknown>[]
  row_count: number
  confidence_score: number
  confidence_level: string
  confidence_indicator: string
  follow_up_questions: string[]
  error_message?: string
  execution_time_ms: number
  status: string
  created_at: string
}

export async function submitNLQuery(
  request: NLQueryRequest
): Promise<NLQueryResult> {
  const token = localStorage.getItem("access_token")
  const response = await fetch(`${API_BASE}/nl/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }))
    throw new Error(error.detail || "Failed to submit query")
  }

  return response.json()
}

export async function getQueryHistory(): Promise<NLQueryResult[]> {
  const token = localStorage.getItem("access_token")
  const response = await fetch(`${API_BASE}/nl/history`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })

  if (!response.ok) throw new Error("Failed to fetch query history")
  const data = await response.json()
  return data.queries || []
}
