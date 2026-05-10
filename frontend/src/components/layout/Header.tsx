import { Link, useNavigate } from "react-router-dom"
import { Button } from "../ui/Button"
import { useAuth } from "../../hooks/useAuth"
import { ForgeLogo } from "../ui/ForgeLogo"

export function Header() {
  const { user, isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()

  function handleLogout() {
    logout()
    navigate("/login", { replace: true })
  }

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-bold text-xl">
          <ForgeLogo className="h-6 w-6" />
          Forge Intelligence
        </Link>

        <nav className="flex items-center gap-4">
          {isAuthenticated ? (
            <>
              <Link to="/dashboard" className="text-sm font-medium">
                Dashboard
              </Link>
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">
                  {user?.email}
                  {user?.role && (
                    <span className="ml-2 rounded-full bg-secondary px-2 py-0.5 text-xs">
                      {user.role}
                    </span>
                  )}
                </span>
                <Button variant="outline" size="sm" onClick={handleLogout}>
                  Sign Out
                </Button>
              </div>
            </>
          ) : (
            <Button variant="outline" size="sm" onClick={() => navigate("/login")}>
              Sign In
            </Button>
          )}
        </nav>
      </div>
    </header>
  )
}
