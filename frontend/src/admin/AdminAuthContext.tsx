/**
 * Admin 認證狀態管理 Context
 * 提供登入/登出/角色檢查/多店切換等功能
 */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import {
  adminLogin,
  adminLogout,
  fetchAdminMe,
  fetchMyStores,
  isAdminLoggedIn,
  type AdminUser,
  type MerchantStore,
} from './api'

const CURRENT_RETAILER_KEY = 'admin_current_retailer_id'

interface AdminAuthContextType {
  admin: AdminUser | null
  loading: boolean
  isLoggedIn: boolean
  isSuperAdmin: boolean
  isAdmin: boolean
  isMerchant: boolean
  /** 多店支援 */
  stores: MerchantStore[]
  currentRetailerId: number | null
  switchStore: (retailerId: number) => void
  login: (username: string, password: string) => Promise<AdminUser>
  logout: () => void
}

const AdminAuthContext = createContext<AdminAuthContextType | null>(null)

/**
 * Admin 認證 Provider
 * 包裹在 Admin 區塊最外層
 */
export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [admin, setAdmin] = useState<AdminUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [stores, setStores] = useState<MerchantStore[]>([])
  const [currentRetailerId, setCurrentRetailerId] = useState<number | null>(null)

  /** 載入多店清單 */
  const loadStores = useCallback(async (user: AdminUser) => {
    if (user.role !== 'MERCHANT') return
    try {
      const list = await fetchMyStores()
      setStores(list)
      // 從 localStorage 恢復上次選擇的店家
      const saved = localStorage.getItem(CURRENT_RETAILER_KEY)
      const savedId = saved ? Number(saved) : null
      if (savedId && list.some(s => s.id === savedId)) {
        setCurrentRetailerId(savedId)
      } else if (list.length > 0) {
        setCurrentRetailerId(list[0].id)
        localStorage.setItem(CURRENT_RETAILER_KEY, String(list[0].id))
      }
    } catch {
      // 向下相容：如果 my-stores API 不存在，用 retailerId
      if (user.retailerId) {
        setCurrentRetailerId(user.retailerId)
      }
    }
  }, [])

  /** 初始化：從 localStorage 恢復登入狀態 */
  useEffect(() => {
    async function restore() {
      if (!isAdminLoggedIn()) {
        setLoading(false)
        return
      }
      try {
        const data = await fetchAdminMe()
        setAdmin(data)
        await loadStores(data)
      } catch {
        adminLogout()
      } finally {
        setLoading(false)
      }
    }
    restore()
  }, [loadStores])

  const login = useCallback(async (username: string, password: string) => {
    const user = await adminLogin(username, password)
    setAdmin(user)
    await loadStores(user)
    return user
  }, [loadStores])

  const logout = useCallback(() => {
    adminLogout()
    localStorage.removeItem(CURRENT_RETAILER_KEY)
    setAdmin(null)
    setStores([])
    setCurrentRetailerId(null)
  }, [])

  const switchStore = useCallback((retailerId: number) => {
    setCurrentRetailerId(retailerId)
    localStorage.setItem(CURRENT_RETAILER_KEY, String(retailerId))
  }, [])

  const value: AdminAuthContextType = {
    admin,
    loading,
    isLoggedIn: !!admin,
    isSuperAdmin: admin?.role === 'SUPER_ADMIN',
    isAdmin: admin?.role === 'ADMIN',
    isMerchant: admin?.role === 'MERCHANT',
    stores,
    currentRetailerId,
    switchStore,
    login,
    logout,
  }

  return (
    <AdminAuthContext.Provider value={value}>
      {children}
    </AdminAuthContext.Provider>
  )
}

/**
 * 取得 Admin 認證狀態的 Hook
 */
export function useAdminAuth(): AdminAuthContextType {
  const ctx = useContext(AdminAuthContext)
  if (!ctx) {
    throw new Error('useAdminAuth 必須在 AdminAuthProvider 內使用')
  }
  return ctx
}
