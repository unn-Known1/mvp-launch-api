import { useState } from "react"
import type { FormEvent } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import { login as apiLogin } from "../services/api"
import { Button } from "../components/ui/Button"
import { Input } from "../components/ui/Input"
import { ErrorBanner } from "../components/ui/ErrorBanner"
import { ForgeLogo } from "../components/ui/ForgeLogo"

export function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || "/dashboard"

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError("")
    setIsLoading(true)

    try {
      const response = await apiLogin({ email, password })
      localStorage.setItem("access_token", response.access_token)
      localStorage.setItem("refresh_token", response.refresh_token)
      localStorage.setItem("token_expires_at", String(Date.now() + response.expires_in * 1000))
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center">
          <ForgeLogo className="mx-auto h-12 w-auto" />
          <h1 className="mt-6 text-3xl font-bold tracking-tight">
            Sign in to Forge Intelligence
          </h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Enter your credentials to access your account
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && <ErrorBanner message={error} onDismiss={() => setError("")} />}

          <div className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-1">
                Email address
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="you@example.com"
                autoComplete="email"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-1">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="Enter your password"
                autoComplete="current-password"
              />
            </div>
          </div>

          <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
            {isLoading ? "Signing in..." : "Sign in"}
          </Button>
        </form>
      </div>
    </div>
  )
}
