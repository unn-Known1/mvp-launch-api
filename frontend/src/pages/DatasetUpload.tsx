import { useState, useCallback } from "react"
import { useNavigate } from "react-router-dom"
import { UploadCloud, ArrowLeft, FileSpreadsheet, CheckCircle, Loader2 } from "lucide-react"
import { Button } from "../components/ui/Button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../components/ui/Card"
import { ErrorBanner } from "../components/ui/ErrorBanner"
import { uploadCsvDataset } from "../services/api"
import type { Dataset, UploadProgress } from "../services/api"

const MAX_FILE_SIZE = 100 * 1024 * 1024 // 100MB

export default function DatasetUpload() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState<UploadProgress | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<Dataset | null>(null)
  const [dragActive, setDragActive] = useState(false)

  const handleFileSelect = useCallback((selectedFile: File) => {
    setError(null)
    if (!selectedFile.name.endsWith(".csv")) {
      setError("Please select a CSV file")
      return
    }
    if (selectedFile.size > MAX_FILE_SIZE) {
      setError(`File size exceeds 100MB limit (${(selectedFile.size / 1024 / 1024).toFixed(1)}MB)`)
      return
    }
    setFile(selectedFile)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) handleFileSelect(droppedFile)
  }, [handleFileSelect])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragActive(true)
  }, [])

  const handleDragLeave = useCallback(() => {
    setDragActive(false)
  }, [])

  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setError(null)
    setProgress(null)

    try {
      const dataset = await uploadCsvDataset(file, (p) => setProgress(p))
      setResult(dataset)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed")
    } finally {
      setUploading(false)
    }
  }

  const handleReset = () => {
    setFile(null)
    setProgress(null)
    setResult(null)
    setError(null)
  }

  if (result) {
    return (
      <div className="space-y-6 max-w-2xl">
        <Button variant="ghost" onClick={() => navigate("/datasets")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Datasets
        </Button>

        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center space-y-4 py-8">
              <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center">
                <CheckCircle className="h-8 w-8 text-green-600" />
              </div>
              <h2 className="text-2xl font-bold">Upload Complete</h2>
              <p className="text-muted-foreground">
                <strong>{result.name}</strong> has been uploaded successfully.
              </p>
              <div className="flex gap-3 mt-4">
                <Button variant="outline" onClick={handleReset}>
                  Upload Another
                </Button>
                <Button onClick={() => navigate(`/datasets/${result.id}`)}>
                  View Dataset
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="sm" onClick={() => navigate("/datasets")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Upload Dataset</h1>
          <p className="text-muted-foreground mt-1">
            Upload a CSV file (max 100MB) to create a new dataset
          </p>
        </div>
      </div>

      {error && <ErrorBanner message={error} />}

      <Card>
        <CardHeader>
          <CardTitle>CSV File Upload</CardTitle>
          <CardDescription>
            Drag and drop your file here, or click to browse
          </CardDescription>
        </CardHeader>
        <CardContent>
          {!file ? (
            <div
              className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
                dragActive
                  ? "border-primary bg-primary/5"
                  : "border-muted-foreground/25 hover:border-muted-foreground/50"
              }`}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onClick={() => document.getElementById("file-input")?.click()}
            >
              <UploadCloud className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-sm font-medium">
                Drop your CSV file here, or <span className="text-primary">browse</span>
              </p>
              <p className="text-xs text-muted-foreground mt-2">
                CSV files up to 100MB
              </p>
              <input
                id="file-input"
                type="file"
                accept=".csv"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleFileSelect(e.target.files[0])}
              />
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3 p-4 border rounded-lg">
                <FileSpreadsheet className="h-8 w-8 text-primary flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{file.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                </div>
                {!uploading && (
                  <Button variant="ghost" size="sm" onClick={handleReset}>
                    Change
                  </Button>
                )}
              </div>

              {uploading && progress && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm">
                    <span>{progress.percentage}% uploaded</span>
                    <span className="text-muted-foreground">
                      {Math.round(progress.loaded / 1024 / 1024 * 10) / 10}MB / {Math.round(progress.total / 1024 / 1024 * 10) / 10}MB
                    </span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary transition-all duration-300"
                      style={{ width: `${progress.percentage}%` }}
                    />
                  </div>
                </div>
              )}

              {uploading && !progress && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Preparing upload...
                </div>
              )}

              {!uploading && (
                <Button onClick={handleUpload} className="w-full">
                  <UploadCloud className="mr-2 h-4 w-4" />
                  Upload Dataset
                </Button>
              )}

              {uploading && (
                <Button disabled className="w-full">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Uploading...
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
