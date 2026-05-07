import { useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { Upload, Search, Trash2, Eye, AlertCircle, FileSpreadsheet } from "lucide-react"
import { Button } from "../components/ui/Button"
import { Input } from "../components/ui/Input"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card"
import { ErrorBanner } from "../components/ui/ErrorBanner"
import { EmptyState } from "../components/ui/EmptyState"
import { useDatasets } from "../hooks/useDatasets"
import { deleteDataset } from "../services/api"
import type { Dataset } from "../services/api"
import { cn } from "../lib/utils"

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

interface DeleteDialogProps {
  dataset: Dataset
  onConfirm: () => void
  onCancel: () => void
}

function DeleteDialog({ dataset, onConfirm, onCancel }: DeleteDialogProps) {
  return (
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
          <Button variant="outline" onClick={onCancel}>Cancel</Button>
          <Button variant="destructive" onClick={onConfirm}>Delete</Button>
        </div>
      </div>
    </div>
  )
}

export function DatasetsList() {
  const navigate = useNavigate()
  const { datasets, total, loading, error, refetch } = useDatasets({ autoFetch: true })
  const [search, setSearch] = useState("")
  const [deleteTarget, setDeleteTarget] = useState<Dataset | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const filteredDatasets = datasets.filter((d) =>
    d.name.toLowerCase().includes(search.toLowerCase()) ||
    (d.description && d.description.toLowerCase().includes(search.toLowerCase()))
  )

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return
    setDeleteError(null)
    try {
      await deleteDataset(deleteTarget.id)
      setDeleteTarget(null)
      refetch()
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "Failed to delete dataset")
    }
  }, [deleteTarget, refetch])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Datasets</h1>
          <p className="text-muted-foreground mt-1">
            Manage your datasets and uploads
          </p>
        </div>
        <Button onClick={() => navigate("/datasets/upload")}>
          <Upload className="mr-2 h-4 w-4" />
          Upload CSV
        </Button>
      </div>

      {error && <ErrorBanner message={error} />}
      {deleteError && <ErrorBanner message={deleteError} />}

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>All Datasets</CardTitle>
              <CardDescription>
                {total} dataset{total !== 1 ? "s" : ""} total
              </CardDescription>
            </div>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search datasets..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9"
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="h-12 bg-muted/50 rounded animate-pulse" />
              ))}
            </div>
          ) : filteredDatasets.length === 0 ? (
            <EmptyState
              icon={<FileSpreadsheet className="h-12 w-12" />}
              title={search ? "No matching datasets" : "No datasets yet"}
              description={search
                ? "Try a different search term"
                : "Upload your first CSV file to get started"}
              action={
                !search ? (
                  <Button onClick={() => navigate("/datasets/upload")}>
                    <Upload className="mr-2 h-4 w-4" />
                    Upload CSV
                  </Button>
                ) : undefined
              }
            />
          ) : (
            <div className="rounded-md border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-3 text-left font-medium">Name</th>
                    <th className="px-4 py-3 text-left font-medium">Rows</th>
                    <th className="px-4 py-3 text-left font-medium">Size</th>
                    <th className="px-4 py-3 text-left font-medium">Status</th>
                    <th className="px-4 py-3 text-left font-medium">Created</th>
                    <th className="px-4 py-3 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDatasets.map((dataset) => (
                    <tr key={dataset.id} className="border-b hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <button
                          onClick={() => navigate(`/datasets/${dataset.id}`)}
                          className="font-medium text-left hover:underline text-primary"
                        >
                          {dataset.name}
                        </button>
                        {dataset.description && (
                          <p className="text-xs text-muted-foreground truncate max-w-xs">
                            {dataset.description}
                          </p>
                        )}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {dataset.row_count.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatBytes(dataset.size_bytes)}
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("inline-flex items-center px-2 py-1 rounded-full text-xs font-medium", getStatusBadgeClass(dataset.status))}>
                          {dataset.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDate(dataset.created_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/datasets/${dataset.id}`)}
                          >
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteTarget(dataset)}
                          >
                            <Trash2 className="h-4 w-4 text-destructive" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {deleteTarget && (
        <DeleteDialog
          dataset={deleteTarget}
          onConfirm={handleDelete}
          onCancel={() => { setDeleteTarget(null); setDeleteError(null) }}
        />
      )}
    </div>
  )
}
