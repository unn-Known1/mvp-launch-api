import { Link } from "react-router-dom"
import { Button } from "../ui/Button"

export function Header() {
  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center justify-between">
        <Link to="/" className="font-bold text-xl">
          Forge Intelligence
        </Link>
        <nav className="flex items-center gap-4">
          <Link to="/dashboard" className="text-sm font-medium">
            Dashboard
          </Link>
          <Link to="/reports" className="text-sm font-medium">
            Reports
          </Link>
          <Button variant="outline" size="sm">
            Sign In
          </Button>
        </nav>
      </div>
    </header>
  )
}
