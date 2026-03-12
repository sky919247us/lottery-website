/**
 * LINE 登入認證 Hook
 * 管理 LINE OAuth 登入狀態與 JWT Token
 */
import { useState, useEffect, useCallback } from 'react'
import {
    loginWithLineCode,
    fetchAuthMe,
    setAuthToken,
    updateProfile,
    type UserData,
} from './api'

const TOKEN_KEY = 'scratchcard_auth_token'
const LINE_CHANNEL_ID = '2009324271'
const LINE_REDIRECT_URI = 'http://localhost:5173/auth/callback'

/**
 * LINE 認證 Hook
 * 提供登入、登出、使用者狀態管理
 */
export function useAuth() {
    const [user, setUser] = useState<UserData | null>(null)
    const [loading, setLoading] = useState(true)
    const [isFirstLogin, setIsFirstLogin] = useState(false)

    /** 初始化：檢查 localStorage 中的 Token */
    useEffect(() => {
        restoreSession()
    }, [])

    /** 從 localStorage 恢復登入狀態 */
    async function restoreSession() {
        const token = localStorage.getItem(TOKEN_KEY)
        if (!token) {
            setLoading(false)
            return
        }

        try {
            setAuthToken(token)
            const userData = await fetchAuthMe()
            setUser(userData)
        } catch {
            // Token 失效，清除
            localStorage.removeItem(TOKEN_KEY)
            setAuthToken(null)
        } finally {
            setLoading(false)
        }
    }

    /** 導向 LINE 授權頁面 */
    const loginWithLine = useCallback(() => {
        // 產生 state 防止 CSRF
        const state = Math.random().toString(36).substring(2)
        sessionStorage.setItem('line_auth_state', state)

        // 記住當前頁面路徑，登入後導回
        sessionStorage.setItem('line_auth_redirect', window.location.pathname)

        const params = new URLSearchParams({
            response_type: 'code',
            client_id: LINE_CHANNEL_ID,
            redirect_uri: LINE_REDIRECT_URI,
            state,
            scope: 'profile openid',
        })

        window.location.href = `https://access.line.me/oauth2/v2.1/authorize?${params.toString()}`
    }, [])

    /** 處理 LINE 回調：用 code 換取 JWT */
    const handleLineCallback = useCallback(async (code: string, state: string) => {
        // 驗證 state
        const savedState = sessionStorage.getItem('line_auth_state')
        if (savedState && savedState !== state) {
            throw new Error('State 驗證失敗，可能的 CSRF 攻擊')
        }
        sessionStorage.removeItem('line_auth_state')

        // 送 code 到後端換取 JWT
        const result = await loginWithLineCode(code)

        // 儲存 Token
        localStorage.setItem(TOKEN_KEY, result.token)
        setAuthToken(result.token)
        setUser(result.user)

        // 判斷是否首次登入（customNickname 等於 displayName 時視為首次）
        if (result.user.customNickname === result.user.displayName) {
            setIsFirstLogin(true)
        }

        return result.user
    }, [])

    /** 登出 */
    const logout = useCallback(() => {
        localStorage.removeItem(TOKEN_KEY)
        setAuthToken(null)
        setUser(null)
    }, [])

    /** 更新暱稱 */
    const setNickname = useCallback(async (nickname: string) => {
        const updated = await updateProfile(nickname)
        setUser(updated)
        setIsFirstLogin(false)
        return updated
    }, [])

    /** 重新拉取使用者最新資料 */
    const refreshUser = useCallback(async () => {
        try {
            const userData = await fetchAuthMe()
            setUser(userData)
        } catch {
            // 靜默處理
        }
    }, [])

    return {
        user,
        loading,
        isLoggedIn: !!user,
        isFirstLogin,
        loginWithLine,
        handleLineCallback,
        logout,
        setNickname,
        refreshUser,
    }
}
