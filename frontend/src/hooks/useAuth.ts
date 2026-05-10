import { useState, useEffect, useCallback } from "react"
import { getToken as apiGetToken, logout as apiLogout } from "../services/api"

interface User {
  id: string
  email: string
  role?: string
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  hasRole: (requiredRole: string | string[]) => boolean
}

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const base64Url = token.split('.')[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

function isValidPayload(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function getStringField(obj: Record<string, unknown>, field: string, fallback: string): string {
  const value = obj[field]
  if (typeof value === 'string' && value.length > 0) return value
  if (typeof value === 'number') return String(value)
  return fallback
}

function getOptionalStringField(obj: Record<string, unknown>, field: string): string | undefined {
  const value = obj[field]
  if (typeof value === 'string' && value.length > 0) return value
  return undefined
}

export function useAuth(): AuthState & { logout: () => void; getToken: () => Promise<string | null> } {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const loadUser = useCallback(() => {
    setIsLoading(true)
    try {
      const token = localStorage.getItem("access_token")
      if (!token) {
        setUser(null)
        setIsLoading(false)
        return
      }

      const payload = decodeJwtPayload(token)
      if (isValidPayload(payload)) {
        setUser({
          id: getStringField(payload, 'sub', getStringField(payload, 'user_id', getStringField(payload, 'id', 'unknown'))),
          email: getStringField(payload, 'email', 'unknown@example.com'),
          role: getOptionalStringField(payload, 'role'),
        })
      } else {
        setUser(null)
      }
    } catch {
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const getToken = useCallback(async (): Promise<string | null> => {
    return await apiGetToken()
  }, [])

  useEffect(() => {
    loadUser()

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "access_token") {
        loadUser()
      }
    }

    window.addEventListener("storage", handleStorageChange)
    return () => window.removeEventListener("storage", handleStorageChange)
  }, [loadUser])

  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } catch (err) {
      // Logout API failed, but we still clear local state
      const errorMessage = err instanceof Error ? err.message : "Logout API failed"
      console.warn(errorMessage)
    }
    localStorage.removeItem("access_token")
    localStorage.removeItem("refresh_token")
    localStorage.removeItem("token_expires_at")
    setUser(null)
  }, [])

  const hasRole = useCallback((requiredRole: string | string[]): boolean => {
    if (!user?.role) return false
    const roles = Array.isArray(requiredRole) ? requiredRole : [requiredRole]
    return roles.includes(user.role)
  }, [user?.role])

  return {
    user,
    isAuthenticated: !!user,
    isLoading,
    hasRole,
    logout,
    getToken,
  }
}
