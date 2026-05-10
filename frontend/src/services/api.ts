const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"

async function getHeaders(includeContentType = true): Promise<Record<string, string>> {
  const headers: Record<string, string> = {}
  if (includeContentType) headers["Content-Type"] = "application/json"

  try {
    const token = await getToken()
    if (token) headers.Authorization = `Bearer ${token}`
  } catch {
    // Token refresh failed, proceed without auth header
  }

  return headers
}

export async function getToken(): Promise<string | null> {
  const token = localStorage.getItem("access_token")
  const expiresAt = localStorage.getItem("token_expires_at")

  if (token && expiresAt) {
    const expiresIn = parseInt(expiresAt) - Date.now()
    if (expiresIn < 60000) {
      return await refreshAccessToken()
    }
    return token
  }

  return await refreshAccessToken()
}

export async function refreshAccessToken(): Promise<string | null> {
  const storedRefreshToken = localStorage.getItem("refresh_token")
  if (!storedRefreshToken) return null

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: storedRefreshToken }),
    })

    if (!response.ok) {
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
      localStorage.removeItem("token_expires_at")
      return null
    }

    const data = await response.json()
    localStorage.setItem("access_token", data.access_token)
    localStorage.setItem("refresh_token", data.refresh_token)
    localStorage.setItem("token_expires_at", String(Date.now() + data.expires_in * 1000))
    return data.access_token
  } catch {
    return null
  }
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface LoginRequest {
  email: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  expires_in: number
}

export async function login(request: LoginRequest): Promise<LoginResponse> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: await getHeaders(),
    body: JSON.stringify(request),
  })
  if (!response.ok) throw new Error("Login failed")
  return response.json()
}

export async function logout(): Promise<void> {
  const token = localStorage.getItem("access_token")
  await fetch(`${API_BASE}/auth/logout`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  })
  localStorage.removeItem("access_token")
  localStorage.removeItem("refresh_token")
  localStorage.removeItem("token_expires_at")
}

// ─── Datasets ────────────────────────────────────────────────────────────────

export interface Dataset {
  id: string
  name: string
  description: string | null
  row_count: number
  size_bytes: number
  status: string
  schema: Record<string, unknown> | null
  created_at: string | null
}

export interface DatasetsListResponse {
  data: Dataset[]
  total: number
}

export async function listDatasets(page = 1, limit = 20): Promise<DatasetsListResponse> {
  const response = await fetch(`${API_BASE}/data?page=${page}&limit=${limit}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch datasets")
  return response.json()
}

export async function getDataset(datasetId: string): Promise<Dataset> {
  const response = await fetch(`${API_BASE}/data/${datasetId}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch dataset")
  return response.json()
}

export async function deleteDataset(datasetId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/data/${datasetId}`, {
    method: "DELETE",
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to delete dataset")
}

export async function listCsvDatasets(): Promise<Dataset[]> {
  const response = await fetch(`${API_BASE}/csv/datasets`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch CSV datasets")
  return response.json()
}

export interface UploadProgress {
  loaded: number
  total: number
  percentage: number
}

export async function uploadCsvDataset(
  file: File,
  onProgress?: (progress: UploadProgress) => void
): Promise<Dataset> {
  const token = await getToken()
  const formData = new FormData()
  formData.append("file", file)

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open("POST", `${API_BASE}/csv/upload`)

    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`)
    }

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && onProgress) {
        onProgress({
          loaded: event.loaded,
          total: event.total,
          percentage: Math.round((event.loaded / event.total) * 100),
        })
      }
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText))
      } else {
        const error = JSON.parse(xhr.responseText).detail || "Upload failed"
        reject(new Error(error))
      }
    }

    xhr.onerror = () => reject(new Error("Network error during upload"))
    xhr.send(formData)
  })
}

// ─── NL Query ────────────────────────────────────────────────────────────────

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

export async function submitNLQuery(request: NLQueryRequest): Promise<NLQueryResult> {
  const response = await fetch(`${API_BASE}/nl/query`, {
    method: "POST",
    headers: await getHeaders(),
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }))
    throw new Error(error.detail || "Failed to submit query")
  }
  return response.json()
}

export async function getQueryHistory(userId: string, limit = 50): Promise<NLQueryResult[]> {
  const response = await fetch(`${API_BASE}/nl/history?user_id=${userId}&limit=${limit}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch query history")
  const data = await response.json()
  return data.queries || []
}

export async function getRecentQueries(userId: string, limit = 10): Promise<NLQueryResult[]> {
  const response = await fetch(`${API_BASE}/nl/recent?user_id=${userId}&limit=${limit}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch recent queries")
  return response.json()
}

// ─── Anomalies ───────────────────────────────────────────────────────────────

export interface Anomaly {
  id: string
  dataset_id: string
  metric_name: string
  timestamp: string
  expected_value: string | null
  actual_value: string
  severity: "low" | "medium" | "high"
  detection_method: string
  z_score: string | null
  iqr_lower: string | null
  iqr_upper: string | null
  status: "flagged" | "investigated" | "dismissed"
  investigated_at: string | null
  investigated_by: string | null
  notes: string | null
  confidence: number | null
  model_version: string | null
  created_at: string
}

export interface AnomalyNotification {
  id: string
  anomaly_id: string
  read: boolean
  created_at: string
  anomaly: Anomaly
}

export interface AnomalyThreshold {
  id: string
  dataset_id: string
  metric_name: string
  z_score_threshold: number
  iqr_multiplier: number
  enabled: boolean
}

export async function listAnomalies(
  filters?: { dataset_id?: string; status?: string; severity?: string }
): Promise<Anomaly[]> {
  const params = new URLSearchParams()
  if (filters?.dataset_id) params.set("dataset_id", filters.dataset_id)
  if (filters?.status) params.set("status", filters.status)
  if (filters?.severity) params.set("severity", filters.severity)
  const response = await fetch(`${API_BASE}/anomalies?${params}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch anomalies")
  return response.json()
}

export async function updateAnomaly(
  anomalyId: string,
  update: { status: "investigated" | "dismissed"; notes?: string }
): Promise<Anomaly> {
  const response = await fetch(`${API_BASE}/anomalies/${anomalyId}`, {
    method: "PATCH",
    headers: await getHeaders(),
    body: JSON.stringify(update),
  })
  if (!response.ok) throw new Error("Failed to update anomaly")
  return response.json()
}

export async function getAnomalyNotifications(unreadOnly = false): Promise<AnomalyNotification[]> {
  const response = await fetch(
    `${API_BASE}/anomalies/notifications?unread_only=${unreadOnly}`,
    { headers: await getHeaders(false) }
  )
  if (!response.ok) throw new Error("Failed to fetch notifications")
  return response.json()
}

export async function markNotificationRead(notificationId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/anomalies/notifications/${notificationId}/read`, {
    method: "POST",
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error("Failed to mark notification as read")
}

export async function listThresholds(): Promise<AnomalyThreshold[]> {
  const response = await fetch(`${API_BASE}/anomalies/thresholds`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch thresholds")
  return response.json()
}

export async function scanAnomalies(
  params?: { dataset_id?: string; metric_name?: string }
): Promise<{ scanned_datasets: number; total_anomalies_found: number; anomalies_by_dataset: Record<string, unknown> }> {
  const qs = params ? `?${new URLSearchParams(params as Record<string, string>)}` : ""
  const response = await fetch(`${API_BASE}/anomalies/scan${qs}`, {
    method: "POST",
    headers: await getHeaders(),
  })
  if (!response.ok) throw new Error("Failed to scan anomalies")
  return response.json()
}

// ─── Forecast ────────────────────────────────────────────────────────────────

export interface ForecastRequest {
  dataset_id: string
  target_column: string
  periods: number
  frequency?: string
}

export interface ForecastResult {
  forecast: Record<string, unknown>[]
  model_metrics: Record<string, unknown>
}

export async function createForecast(request: ForecastRequest): Promise<ForecastResult> {
  const response = await fetch(`${API_BASE}/ml/forecast`, {
    method: "POST",
    headers: await getHeaders(),
    body: JSON.stringify(request),
  })
  if (!response.ok) throw new Error("Failed to create forecast")
  return response.json()
}

export async function getForecast(forecastId: string): Promise<ForecastResult> {
  const response = await fetch(`${API_BASE}/ml/forecast/${forecastId}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch forecast")
  return response.json()
}

// ─── Reports ─────────────────────────────────────────────────────────────────

export interface ReportTemplate {
  id: string
  user_id: string
  name: string
  description: string | null
  config: Record<string, unknown>
  created_at: string
  updated_at: string | null
}

export interface ScheduledReport {
  id: string
  user_id: string
  template_id: string | null
  name: string
  description: string | null
  frequency: string
  time_of_day: string
  timezone: string
  recipients: string[]
  is_active: boolean
  last_run_at: string | null
  next_run_at: string | null
  config: Record<string, unknown>
  created_at: string
  updated_at: string | null
}

export interface ReportDelivery {
  id: string
  scheduled_report_id: string
  status: string
  delivered_at: string | null
  error_message: string | null
  pdf_url: string | null
  csv_urls: string[]
  ai_summary: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

export async function listReportTemplates(userId: string): Promise<ReportTemplate[]> {
  const response = await fetch(`${API_BASE}/reports/templates?user_id=${userId}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch report templates")
  return response.json()
}

export async function listScheduledReports(
  userId: string,
  isActive?: boolean
): Promise<ScheduledReport[]> {
  const params = new URLSearchParams({ user_id: userId })
  if (isActive !== undefined) params.set("is_active", String(isActive))
  const response = await fetch(`${API_BASE}/reports/scheduled?${params}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch scheduled reports")
  return response.json()
}

export async function listReportDeliveries(
  userId: string,
  reportId?: string,
  status?: string
): Promise<ReportDelivery[]> {
  const params = new URLSearchParams({ user_id: userId })
  if (reportId) params.set("report_id", reportId)
  if (status) params.set("status", status)
  const response = await fetch(`${API_BASE}/reports/deliveries?${params}`, {
    headers: await getHeaders(false),
  })
  if (!response.ok) throw new Error("Failed to fetch report deliveries")
  return response.json()
}
