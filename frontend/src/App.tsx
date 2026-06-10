import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import CoLoginPage from './pages/co/CoLoginPage'
import CoAdminPage from './pages/co/CoAdminPage'
import CoInvoicesPage from './pages/co/CoInvoicesPage'
import CoWriteoffPage from './pages/co/CoWriteoffPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<CoLoginPage />} />
        <Route path="/admin" element={<CoAdminPage />} />
        <Route path="/invoices" element={<CoInvoicesPage />} />
        <Route path="/writeoffs" element={<CoWriteoffPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
