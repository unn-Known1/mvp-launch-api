import { lazy, Suspense } from "react"
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { AppLayout } from "./components/layouts/AppLayout"
import { Login } from "./pages/Login"
import { ProtectedRoute } from "./components/auth/ProtectedRoute"
import { RoleBasedRoute } from "./components/auth/RoleBasedRoute"
import { ErrorBoundary } from "./components/ErrorBoundary"
import { useAuth } from "./hooks/useAuth"

const Home = lazy(() => import("./pages/Home"))
const Dashboard = lazy(() => import("./pages/Dashboard"))
const QueryPage = lazy(() => import("./pages/QueryPage"))
const DatasetsList = lazy(() => import("./pages/DatasetsList"))
const DatasetDetail = lazy(() => import("./pages/DatasetDetail"))
const DatasetUpload = lazy(() => import("./pages/DatasetUpload"))
const AnomaliesPage = lazy(() => import("./pages/AnomaliesPage"))
const ForecastsPage = lazy(() => import("./pages/ForecastsPage"))
const ReportsPage = lazy(() => import("./pages/ReportsPage"))

function PageLoader() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  )
}

function App() {
  const { isLoading } = useAuth()

  if (isLoading) {
    return <PageLoader />
  }

  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
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
              <Route
                path="forecasts"
                element={
                  <RoleBasedRoute allowedRoles={["admin", "analyst", "viewer"]}>
                    <ForecastsPage />
                  </RoleBasedRoute>
                }
              />
              <Route
                path="reports"
                element={
                  <RoleBasedRoute allowedRoles={["admin", "analyst"]}>
                    <ReportsPage />
                  </RoleBasedRoute>
                }
              />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
