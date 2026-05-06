import { BrowserRouter, Routes, Route } from "react-router-dom"
import { AppLayout } from "./components/layouts/AppLayout"
import { Home } from "./pages/Home"
import { Dashboard } from "./pages/Dashboard"
import { QueryPage } from "./pages/QueryPage"

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/query" element={<QueryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
