/**
 * 匿名使用者管理 Hook（向下相容封裝）
 * 改用 useAuth 作為底層，不再使用 deviceId
 */
import { useAuth } from './useAuth'

/**
 * 使用者 Hook
 * 封裝 useAuth，提供向下相容的介面
 */
export function useUser() {
    const { user, loading, refreshUser } = useAuth()
    return { user, loading, refreshUser }
}
