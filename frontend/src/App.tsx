import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import CoLoginPage from './pages/co/CoLoginPage'
import CoAdminPage from './pages/co/CoAdminPage'
import CoInvoicesPage from './pages/co/CoInvoicesPage'
import CoWriteoffPage from './pages/co/CoWriteoffPage'
import CoDashboardPage from './pages/co/CoDashboardPage'
import CoReconciliationPage from './pages/co/CoReconciliationPage'
import AuthCallback from './pages/AuthCallback'
import Onboarding from './pages/Onboarding'
import IikoSettingsPage from './pages/co/IikoSettingsPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login"     element={<CoLoginPage />} />
        <Route path="/dashboard" element={<CoDashboardPage />} />
        <Route path="/admin"     element={<CoAdminPage />} />
        <Route path="/invoices"  element={<CoInvoicesPage />} />
        <Route path="/writeoffs" element={<CoWriteoffPage />} />
        <Route path="/reconciliation" element={<CoReconciliationPage />} />
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/integrations" element={<IikoSettingsPage />} />
        <Route path="*"          element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
