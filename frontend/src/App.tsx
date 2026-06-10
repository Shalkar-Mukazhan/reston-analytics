import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import CoLoginPage from './pages/co/CoLoginPage'
import CoAdminPage from './pages/co/CoAdminPage'
import CoInvoicesPage from './pages/co/CoInvoicesPage'
import CoWriteoffPage from './pages/co/CoWriteoffPage'
import DashboardPage from './pages/DashboardPage'
import ReportsPage from './pages/ReportsPage'
import InvoicesPage from './pages/InvoicesPage'
import Invoices2Page from './pages/Invoices2Page'
import AdminPage from './pages/AdminPage'
import AnalyticsPage from './pages/AnalyticsPage'
import PlanningPage from './pages/PlanningPage'
import ChecklistPage from './pages/ChecklistPage'
import AboutPage from './pages/AboutPage'
import { Loader2 } from 'lucide-react'

function PrivateRoute({ children, adminOnly }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen bg-brand-bg flex items-center justify-center">
        <Loader2 size={28} className="animate-spin text-brand-muted" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  if (adminOnly && user.role !== 'co' && user.role !== 'admin') return <Navigate to="/dashboard" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="invoices" element={<InvoicesPage />} />
          <Route path="invoices2" element={<Invoices2Page />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="planning" element={<PlanningPage />} />
          <Route path="checklist" element={<ChecklistPage />} />
          <Route path="about" element={<AboutPage />} />
          <Route
            path="admin"
            element={
              <PrivateRoute adminOnly>
                <AdminPage />
              </PrivateRoute>
            }
          />
        </Route>
        {/* Coffee Original */}
        <Route path="/co/login" element={<CoLoginPage />} />
        <Route path="/co/admin" element={<CoAdminPage />} />
        <Route path="/co/invoices" element={<CoInvoicesPage />} />
        <Route path="/co/writeoffs" element={<CoWriteoffPage />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
