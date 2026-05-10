import { AlertTriangle, X } from "lucide-react"
import { cn } from "../../lib/utils"

interface ErrorBannerProps {
  message: string
  onDismiss?: () => void
  className?: string
}

export function ErrorBanner({ message, onDismiss, className }: ErrorBannerProps) {
  return (
    <div className={cn(
      "flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3",
      className
    )}>
      <AlertTriangle className="h-5 w-5 text-red-600 flex-shrink-0" />
      <p className="text-sm text-red-800 flex-1">{message}</p>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-red-600 hover:text-red-800 transition-colors"
          aria-label="Dismiss error"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}
