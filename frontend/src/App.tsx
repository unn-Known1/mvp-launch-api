import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { AppLayout } from "./components/layouts/AppLayout"
import { Home } from "./pages/Home"
import { Dashboard } from "./pages/Dashboard"
import { QueryPage } from "./pages/QueryPage"
import { DatasetsList } from "./pages/DatasetsList"
import { DatasetDetail } from "./pages/DatasetDetail"
import { DatasetUpload } from "./pages/DatasetUpload"
import { AnomaliesPage } from "./pages/AnomaliesPage"
import { Login } from "./pages/Login"
import { ProtectedRoute } from "./components/auth/ProtectedRoute"
import { RoleBasedRoute } from "./components/auth/RoleBasedRoute"
import { useAuth } from "./hooks/useAuth"

function App() {
  const { isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Home />} />
          <Route
            path="dashboard"
            element={
              <RoleBasedRoute allowedRoles={["admin", "analyst", "viewer"]}>
                <Dashboard />
              </RoleBasedRoute>
            }
          />
          <Route
            path="query"
            element={
              <RoleBasedRoute allowedRoles={["admin", "analyst"]}>
                <QueryPage />
              </RoleBasedRoute>
            }
          />
          <Route
            path="datasets"
            element={
              <RoleBasedRoute allowedRoles={["admin", "analyst", "viewer"]}>
                <DatasetsList />
              </RoleBasedRoute>
            }
          />
          <Route
            path="datasets/upload"
            element={
              <RoleBasedRoute allowedRoles={["admin", "analyst"]}>
                <DatasetUpload />
              </RoleBasedRoute>
            }
          />
          <Route
            path="datasets/:id"
            element={
              <RoleBasedRoute allowedRoles={["admin", "analyst", "viewer"]}>
                <DatasetDetail />
              </RoleBasedRoute>
            }
          />
          <Route
            path="anomalies"
            element={
              <RoleBasedRoute allowedRoles={["admin", "analyst", "viewer"]}>
                <AnomaliesPage />
              </RoleBasedRoute>
            }
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
