import { cn } from "../../lib/utils"

interface Column<T> {
  key: keyof T
  header: string
  className?: string
}

interface DataTableProps<T> {
  data: T[]
  columns: Column<T>[]
  className?: string
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  className,
}: DataTableProps<T>) {
  return (
    <div className={cn("rounded-md border", className)}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            {columns.map((col) => (
              <th key={String(col.key)} className={cn("px-4 py-3 text-left font-medium", col.className)}>
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => (
            <tr key={i} className="border-b">
              {columns.map((col) => (
                <td key={String(col.key)} className="px-4 py-3">
                  {String(row[col.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
