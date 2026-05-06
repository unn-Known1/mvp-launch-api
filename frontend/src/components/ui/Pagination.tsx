import * as React from "react"
import { ChevronLeft, ChevronRight, MoreHorizontal } from "lucide-react"
import { cn } from "../../lib/utils"

export interface PaginationProps extends React.HTMLAttributes<HTMLElement> {
  currentPage: number
  totalPages: number
  onPageChange: (page: number) => void
  siblingCount?: number
}

const Pagination = React.forwardRef<HTMLElement, PaginationProps>(
  ({ className, currentPage, totalPages, onPageChange, siblingCount = 1, ...props }, ref) => {
    const range = (start: number, end: number): number[] => {
      const length = end - start + 1
      return Array.from({ length }, (_, i) => start + i)
    }

    const getPageNumbers = (): (number | "ellipsis-start" | "ellipsis-end")[] => {
      const totalNumbers = siblingCount * 2 + 3
      const totalBlocks = totalNumbers + 2

      if (totalPages <= totalBlocks) {
        return range(1, totalPages)
      }

      const leftSiblingIndex = Math.max(currentPage - siblingCount, 1)
      const rightSiblingIndex = Math.min(currentPage + siblingCount, totalPages)

      const shouldShowLeftEllipsis = leftSiblingIndex > 2
      const shouldShowRightEllipsis = rightSiblingIndex < totalPages - 1

      if (!shouldShowLeftEllipsis && shouldShowRightEllipsis) {
        const leftItemCount = 3 + 2 * siblingCount
        const leftRange = range(1, leftItemCount)
        return [...leftRange, "ellipsis-end", totalPages]
      }

      if (shouldShowLeftEllipsis && !shouldShowRightEllipsis) {
        const rightItemCount = 3 + 2 * siblingCount
        const rightRange = range(totalPages - rightItemCount + 1, totalPages)
        return [1, "ellipsis-start", ...rightRange]
      }

      if (shouldShowLeftEllipsis && shouldShowRightEllipsis) {
        const middleRange = range(leftSiblingIndex, rightSiblingIndex)
        return [1, "ellipsis-start", ...middleRange, "ellipsis-end", totalPages]
      }

      return range(1, totalPages)
    }

    const pages = getPageNumbers()

    const handlePageChange = (page: number) => {
      if (page >= 1 && page <= totalPages && page !== currentPage) {
        onPageChange(page)
      }
    }

    const handleKeyDown = (e: React.KeyboardEvent, page: number) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault()
        handlePageChange(page)
      }
    }

    return (
      <nav
        ref={ref}
        role="navigation"
        aria-label="Pagination"
        className={cn("mx-auto flex w-full justify-center", className)}
        {...props}
      >
        <ul className="flex flex-wrap items-center gap-1" role="list">
          <li>
            <button
              onClick={() => handlePageChange(currentPage - 1)}
              disabled={currentPage <= 1}
              aria-label="Go to previous page"
              className={cn(
                "inline-flex h-9 w-9 items-center justify-center rounded-md border border-input bg-background text-sm font-medium ring-offset-background transition-colors",
                "hover:bg-accent hover:text-accent-foreground",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                "disabled:pointer-events-none disabled:opacity-50"
              )}
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </li>

          {pages.map((page, index) => {
            if (page === "ellipsis-start" || page === "ellipsis-end") {
              return (
                <li key={`ellipsis-${index}`} aria-hidden="true">
                  <span
                    className={cn(
                      "inline-flex h-9 w-9 items-center justify-center text-sm",
                      "hidden md:inline-flex"
                    )}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </span>
                </li>
              )
            }

            const isActive = page === currentPage

            return (
              <li key={page}>
                <button
                  onClick={() => handlePageChange(page)}
                  onKeyDown={(e) => handleKeyDown(e, page)}
                  aria-label={`Go to page ${page}`}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "inline-flex h-9 min-w-[36px] items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors",
                    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                    isActive
                      ? "bg-primary text-primary-foreground hover:bg-primary/90"
                      : "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
                    "hidden md:inline-flex"
                  )}
                >
                  {page}
                </button>
              </li>
            )
          })}

          <li className="md:hidden">
            <span className="inline-flex h-9 items-center justify-center px-3 text-sm font-medium">
              {currentPage} / {totalPages}
            </span>
          </li>

          <li>
            <button
              onClick={() => handlePageChange(currentPage + 1)}
              disabled={currentPage >= totalPages}
              aria-label="Go to next page"
              className={cn(
                "inline-flex h-9 w-9 items-center justify-center rounded-md border border-input bg-background text-sm font-medium ring-offset-background transition-colors",
                "hover:bg-accent hover:text-accent-foreground",
                "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                "disabled:pointer-events-none disabled:opacity-50"
              )}
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </li>
        </ul>
      </nav>
    )
  }
)

Pagination.displayName = "Pagination"

export { Pagination }
