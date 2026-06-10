import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import CoLoginPage from './pages/co/CoLoginPage'
import CoAdminPage from './pages/co/CoAdminPage'
import CoInvoicesPage from './pages/co/CoInvoicesPage'
import CoWriteoffPage from './pages/co/CoWriteoffPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/co/login" element={<CoLoginPage />} />
        <Route path="/co/admin" element={<CoAdminPage />} />
        <Route path="/co/invoices" element={<CoInvoicesPage />} />
        <Route path="/co/writeoffs" element={<CoWriteoffPage />} />
        <Route path="*" element={<Navigate to="/co/login" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
