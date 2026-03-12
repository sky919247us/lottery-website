/**
 * Admin 認證狀態管理 Context
 * 提供登入/登出/角色檢查等功能
 */
import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import {
  adminLogin,
  adminLogout,
  fetchAdminMe,
  isAdminLoggedIn,
  type AdminUser,
} from './api'

interface AdminAuthContextType {
  admin: AdminUser | null
  loading: boolean
  isLoggedIn: boolean
  isSuperAdmin: boolean
  isAdmin: boolean
  isMerchant: boolean
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
      } catch {
        adminLogout()
      } finally {
        setLoading(false)
      }
    }
    restore()
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const user = await adminLogin(username, password)
    setAdmin(user)
    return user
  }, [])

  const logout = useCallback(() => {
    adminLogout()
    setAdmin(null)
  }, [])

  const value: AdminAuthContextType = {
    admin,
    loading,
    isLoggedIn: !!admin,
    isSuperAdmin: admin?.role === 'SUPER_ADMIN',
    isAdmin: admin?.role === 'ADMIN',
    isMerchant: admin?.role === 'MERCHANT',
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
