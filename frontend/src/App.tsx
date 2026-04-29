/**
 * App 根元件
 * 設定路由與全域 Layout
 * /admin/* 路徑使用獨立的管理後台 Layout
 * 使用 React.lazy 實作頁面級懶載入，優化首次載入效能
 */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { SnackbarProvider } from 'notistack'
import NavBar from './components/ui/NavBar'
import Footer from './components/ui/Footer'
import MobileTabBar from './components/ui/MobileTabBar'
import Home from './pages/Home'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false, // 停用預設的切換視窗重新獲取
      retry: 1,
    },
  },
})


// 懶載入：非首頁的大型頁面元件
const Detail = lazy(() => import('./pages/Detail'))
const Videos = lazy(() => import('./pages/Videos'))
const Calculator = lazy(() => import('./pages/Calculator'))
const PnLDashboard = lazy(() => import('./pages/PnLDashboard'))
const CommunityMap = lazy(() => import('./pages/CommunityMap'))
const MerchantDashboard = lazy(() => import('./pages/MerchantDashboard'))
const AuthCallback = lazy(() => import('./pages/AuthCallback'))
const UserProfile = lazy(() => import('./pages/UserProfile'))
const LevelRules = lazy(() => import('./pages/LevelRules'))
const MerchantClaimForm = lazy(() => import('./pages/MerchantClaimForm'))
const StorePage = lazy(() => import('./pages/StorePage'))
const Favorites = lazy(() => import('./pages/Favorites'))
const ContactPage = lazy(() => import('./pages/LegalPages').then(m => ({ default: m.ContactPage })))
const RefundPolicyPage = lazy(() => import('./pages/LegalPages').then(m => ({ default: m.RefundPolicyPage })))
const DeliveryPolicyPage = lazy(() => import('./pages/LegalPages').then(m => ({ default: m.DeliveryPolicyPage })))
const AdminRoutes = lazy(() => import('./admin/AdminRoutes'))

/** 載入中的 Fallback UI */
function PageLoader() {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '60vh',
      color: '#94a3b8',
      fontSize: '0.95rem',
      gap: '0.5rem',
    }}>
      <div className="spinner" />
      載入中...
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <SnackbarProvider
        maxSnack={3}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
        autoHideDuration={3000}
      >
        <BrowserRouter>

      <Routes>
        {/* Admin 後台：獨立 Layout，不使用前台的 NavBar/Footer */}
        <Route path="/admin/*" element={<Suspense fallback={<PageLoader />}><AdminRoutes /></Suspense>} />

        {/* 前台頁面：使用原有 Layout */}
        <Route
          path="*"
          element={
            <>
              <NavBar />
              <main style={{ flex: 1 }}>
                <Suspense fallback={<PageLoader />}>
                  <Routes>
                    <Route path="/" element={<Home />} />
                    <Route path="/detail/:id" element={<Detail />} />
                    <Route path="/videos" element={<Videos />} />
                    <Route path="/calculator" element={<Calculator />} />
                    <Route path="/wallet" element={<PnLDashboard />} />
                    <Route path="/map" element={<CommunityMap />} />
                    <Route path="/merchant" element={<Navigate to="/admin/" replace />} />
                    <Route path="/merchant/claim/:id" element={<MerchantClaimForm />} />
                    <Route path="/auth/callback" element={<AuthCallback />} />
                    <Route path="/profile" element={<UserProfile />} />
                    <Route path="/levels" element={<LevelRules />} />
                    <Route path="/store/:id" element={<StorePage />} />
                    <Route path="/favorites" element={<Favorites />} />
                    <Route path="/contact" element={<ContactPage />} />
                    <Route path="/refund-policy" element={<RefundPolicyPage />} />
                    <Route path="/delivery-policy" element={<DeliveryPolicyPage />} />
                  </Routes>
                </Suspense>
              </main>
              <Footer />
              <MobileTabBar />
            </>
          }
        />
        </Routes>
      </BrowserRouter>
    </SnackbarProvider>
  </QueryClientProvider>
  )
}
