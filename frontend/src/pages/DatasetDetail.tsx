import { useState, useEffect, useCallback } from "react"
import { useParams, useNavigate } from "react-router-dom"
import { Database, ArrowLeft, Trash2, AlertCircle, FileSpreadsheet, Hash, Type, Calendar } from "lucide-react"
import { Button } from "../components/ui/Button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card"
import { ErrorBanner } from "../components/ui/ErrorBanner"
import { getDataset, deleteDataset } from "../services/api"
import type { Dataset } from "../services/api"

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B"
  const k = 1024
  const sizes = ["B", "KB", "MB", "GB"]
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—"
  return new Date(dateStr).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function getStatusBadgeClass(status: string): string {
  switch (status) {
    case "ready": return "bg-green-100 text-green-700"
    case "processing": return "bg-yellow-100 text-yellow-700"
    case "error": return "bg-red-100 text-red-700"
    default: return "bg-gray-100 text-gray-700"
  }
}

export function DatasetDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [deleteLoading, setDeleteLoading] = useState(false)
  const [showDeleteDialog, setShowDeleteDialog] = useState(false)

  const fetchDataset = useCallback(async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const data = await getDataset(id)
      setDataset(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch dataset")
    } finally {
      setLoading(false)
    }
  }, [id])

  useEffect(() => {
    fetchDataset()
  }, [fetchDataset])

  const handleDelete = async () => {
    if (!id) return
    setDeleteLoading(true)
    try {
      await deleteDataset(id)
      navigate("/datasets")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete dataset")
      setShowDeleteDialog(false)
    } finally {
      setDeleteLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-muted/50 rounded w-48 animate-pulse" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[...Array(2)].map((_, i) => (
            <div key={i} className="h-48 bg-muted/50 rounded animate-pulse" />
          ))}
        </div>
      </div>
    )
  }

  if (error || !dataset) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/datasets")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Datasets
        </Button>
        <ErrorBanner message={error || "Dataset not found"} />
      </div>
    )
  }

  const schemaEntries = dataset.schema ? Object.entries(dataset.schema as Record<string, string>) : []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate("/datasets")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold tracking-tight">{dataset.name}</h1>
            {dataset.description && (
              <p className="text-muted-foreground mt-1">{dataset.description}</p>
            )}
          </div>
        </div>
        <Button
          variant="destructive"
          onClick={() => setShowDeleteDialog(true)}
        >
          <Trash2 className="mr-2 h-4 w-4" />
          Delete
        </Button>
      </div>

      {error && <ErrorBanner message={error} />}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileSpreadsheet className="h-5 w-5" />
              Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex justify-between">
              <span className="text-muted-foreground text-sm">Status</span>
              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusBadgeClass(dataset.status)}`}>
                {dataset.status}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground text-sm flex items-center gap-1">
                <Hash className="h-3 w-3" />
                Row Count
              </span>
              <span className="font-medium">{dataset.row_count.toLocaleString()}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground text-sm flex items-center gap-1">
                <Database className="h-3 w-3" />
                Size
              </span>
              <span className="font-medium">{formatBytes(dataset.size_bytes)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground text-sm flex items-center gap-1">
                <Calendar className="h-3 w-3" />
                Created
              </span>
              <span className="font-medium">{formatDate(dataset.created_at)}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Type className="h-5 w-5" />
              Schema
            </CardTitle>
            <CardDescription>
              Column names and detected data types
            </CardDescription>
          </CardHeader>
          <CardContent>
            {schemaEntries.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <AlertCircle className="h-8 w-8 mx-auto mb-2" />
                <p>No schema information available</p>
              </div>
            ) : (
              <div className="rounded-md border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b bg-muted/50">
                      <th className="px-4 py-3 text-left font-medium">Column</th>
                      <th className="px-4 py-3 text-left font-medium">Type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {schemaEntries.map(([column, type], i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="px-4 py-3 font-mono text-sm">{column}</td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center px-2 py-1 rounded bg-muted text-xs font-medium">
                            {String(type)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {showDeleteDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-lg max-w-md w-full mx-4 p-6">
            <div className="flex items-center gap-3 mb-4">
              <AlertCircle className="h-6 w-6 text-destructive" />
              <h3 className="text-lg font-semibold">Delete Dataset</h3>
            </div>
            <p className="text-sm text-muted-foreground mb-6">
              Are you sure you want to delete <strong>{dataset.name}</strong>? This action cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="outline" onClick={() => setShowDeleteDialog(false)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={deleteLoading}
              >
                {deleteLoading ? "Deleting..." : "Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
