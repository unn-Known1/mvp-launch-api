import { cn } from "../../lib/utils"
import type { LucideIcon } from "lucide-react"

interface StatCardProps {
  title: string
  value: string | number
  description?: string
  icon?: LucideIcon
  trend?: {
    value: number
    label: string
  }
  className?: string
}

export function StatCard({ title, value, description, icon: Icon, trend, className }: StatCardProps) {
  return (
    <div className={cn("rounded-lg border bg-card p-6 shadow-sm", className)}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </div>
      <div className="space-y-1">
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {trend && (
        <div className="mt-4 flex items-center gap-1 text-sm">
          <span
            className={cn(
              "font-medium",
              trend.value >= 0 ? "text-emerald-600" : "text-red-600"
            )}
          >
            {trend.value >= 0 ? "+" : ""}
            {trend.value}%
          </span>
          <span className="text-muted-foreground">{trend.label}</span>
        </div>
      )}
    </div>
  )
}
