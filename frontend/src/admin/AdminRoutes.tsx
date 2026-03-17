/**
 * Admin 路由設定
 * 統一管理後台的路由結構與 Guard
 */
import { Routes, Route, Navigate } from 'react-router-dom'
import { ThemeProvider } from '@mui/material/styles'
import { CssBaseline } from '@mui/material'
import adminTheme from './theme'
import { AdminAuthProvider, useAdminAuth } from './AdminAuthContext'
import AdminLayout from './AdminLayout'
import AdminLogin from './pages/AdminLogin'
import AdminDashboard from './pages/AdminDashboard'
import AdminRetailers from './pages/AdminRetailers'
import AdminScratchcards from './pages/AdminScratchcards'
import AdminClaims from './pages/AdminClaims'
import AdminUsers from './pages/AdminUsers'
import AdminAccounts from './pages/AdminAccounts'
import MerchantDashboard from './pages/MerchantDashboard'
import MerchantProfile from './pages/MerchantProfile'
import MerchantInventory from './pages/MerchantInventory'
import MerchantStorePage from './pages/MerchantStorePage'

/**
 * Auth Guard：未登入則導向登入頁
 */
function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isLoggedIn, loading } = useAdminAuth()

  if (loading) {
    return null // NOTE: 等待認證狀態恢復
  }

  if (!isLoggedIn) {
    return <Navigate to="/admin/login" replace />
  }

  return <>{children}</>
}

/**
 * Role Guard：限制特定角色才能存取
 */
function RoleGuard({
  children,
  allowed,
}: {
  children: React.ReactNode
  allowed: string[]
}) {
  const { admin } = useAdminAuth()

  if (!admin || !allowed.includes(admin.role)) {
    return <Navigate to="/admin/dashboard" replace />
  }

  return <>{children}</>
}

/**
 * Admin 路由根元件
 */
function AdminRoutesInner() {
  return (
    <Routes>
      {/* 登入頁 - 獨立 Layout */}
      <Route path="/login" element={<AdminLogin />} />

      {/* 需要認證的頁面 */}
      <Route
        element={
          <AuthGuard>
            <AdminLayout />
          </AuthGuard>
        }
      >
        {/* 管理員視角 */}
        <Route path="/dashboard" element={<AdminDashboard />} />
        <Route path="/retailers" element={<AdminRetailers />} />
        <Route path="/scratchcards" element={<AdminScratchcards />} />
        <Route path="/claims" element={<AdminClaims />} />

        {/* 超級管理員專屬 */}
        <Route
          path="/users"
          element={
            <RoleGuard allowed={['SUPER_ADMIN']}>
              <AdminUsers />
            </RoleGuard>
          }
        />
        <Route
          path="/accounts"
          element={
            <RoleGuard allowed={['SUPER_ADMIN']}>
              <AdminAccounts />
            </RoleGuard>
          }
        />

        {/* 商家視角 */}
        <Route path="/merchant/dashboard" element={<MerchantDashboard />} />
        <Route path="/merchant/profile" element={<MerchantProfile />} />
        <Route path="/merchant/inventory" element={<MerchantInventory />} />
        <Route path="/merchant/store-page" element={<MerchantStorePage />} />

        {/* 預設導向 Dashboard */}
        <Route path="/" element={<Navigate to="/admin/dashboard" replace />} />
      </Route>
    </Routes>
  )
}

/**
 * Admin 路由入口（含 ThemeProvider 與 AuthProvider）
 */
export default function AdminRoutes() {
  return (
    <ThemeProvider theme={adminTheme}>
      <CssBaseline />
      <AdminAuthProvider>
        <AdminRoutesInner />
      </AdminAuthProvider>
    </ThemeProvider>
  )
}
