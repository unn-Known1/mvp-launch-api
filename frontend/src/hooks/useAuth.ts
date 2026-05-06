import { useState, useEffect, useCallback } from "react"

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"

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

async function refreshToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("refresh_token")
  if (!refreshToken) return null

  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!response.ok) {
      localStorage.removeItem("access_token")
      localStorage.removeItem("refresh_token")
      localStorage.removeItem("token_expires_at")
      return null
    }

    const data = await response.json()
    localStorage.setItem("access_token", data.access_token)
    localStorage.setItem("refresh_token", data.refresh_token)
    localStorage.setItem("token_expires_at", String(Date.now() + data.expires_in * 1000))
    return data.access_token
  } catch {
    return null
  }
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
      if (payload) {
        setUser({
          id: (payload.sub || payload.user_id || payload.id || "unknown") as string,
          email: (payload.email || "unknown@example.com") as string,
          role: payload.role as string | undefined,
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
    const token = localStorage.getItem("access_token")
    const expiresAt = localStorage.getItem("token_expires_at")

    if (token && expiresAt) {
      const expiresIn = parseInt(expiresAt) - Date.now()
      if (expiresIn < 60000) {
        return await refreshToken()
      }
      return token
    }

    return await refreshToken()
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

  const logout = useCallback(() => {
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
