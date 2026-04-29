/**
 * LINE 登入回調頁面
 * 處理 LINE OAuth 回傳的 code，完成登入後導回原頁面
 */
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import './AuthCallback.css'

export default function AuthCallback() {
    const navigate = useNavigate()
    const { handleLineCallback, setNickname } = useAuth()
    const [status, setStatus] = useState<'loading' | 'nickname' | 'error'>('loading')
    const [error, setError] = useState('')
    const [nickname, setNicknameInput] = useState('')
    const calledRef = useRef(false)

    async function processCallback() {
        // 防止 React StrictMode 或路由重 mount 導致 code 被重複使用
        if (calledRef.current) return
        calledRef.current = true
        const params = new URLSearchParams(window.location.search)
        const code = params.get('code')
        const state = params.get('state') || ''
        const errorParam = params.get('error')

        if (errorParam) {
            setStatus('error')
            setError('LINE 授權被取消')
            return
        }

        if (!code) {
            setStatus('error')
            setError('缺少授權碼')
            return
        }

        try {
            const user = await handleLineCallback(code, state)

            // 首次登入：顯示設定暱稱的畫面
            if (user.customNickname === user.displayName) {
                setNicknameInput(user.displayName)
                setStatus('nickname')
                return
            }

            // 導回原頁面
            const redirect = sessionStorage.getItem('line_auth_redirect') || '/'
            sessionStorage.removeItem('line_auth_redirect')
            navigate(redirect, { replace: true })
        } catch (err: unknown) {
            setStatus('error')
            setError(err instanceof Error ? err.message : '登入失敗')
        }
    }

    useEffect(() => {
        processCallback()
    }, [])

    /** 儲存暱稱並導回 */
    async function handleSaveNickname() {
        if (!nickname.trim()) return
        try {
            await setNickname(nickname.trim())
            const redirect = sessionStorage.getItem('line_auth_redirect') || '/'
            sessionStorage.removeItem('line_auth_redirect')
            navigate(redirect, { replace: true })
        } catch {
            setError('暱稱儲存失敗')
        }
    }

    if (status === 'loading') {
        return (
            <div className="auth-callback">
                <div className="auth-callback__card">
                    <div className="auth-callback__spinner" />
                    <p>正在完成 LINE 登入...</p>
                </div>
            </div>
        )
    }

    if (status === 'nickname') {
        return (
            <div className="auth-callback">
                <div className="auth-callback__card">
                    <h2>🎉 歡迎加入刮刮研究室！</h2>
                    <p className="auth-callback__subtitle">設定您的刮友暱稱</p>
                    <input
                        className="auth-callback__input"
                        type="text"
                        placeholder="輸入暱稱..."
                        value={nickname}
                        onChange={(e) => setNicknameInput(e.target.value)}
                        maxLength={50}
                        autoFocus
                    />
                    <button
                        className="auth-callback__btn"
                        onClick={handleSaveNickname}
                        disabled={!nickname.trim()}
                    >
                        開始探索 🚀
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div className="auth-callback">
            <div className="auth-callback__card auth-callback__card--error">
                <h2>😥 登入失敗</h2>
                <p>{error}</p>
                <button
                    className="auth-callback__btn"
                    onClick={() => navigate('/', { replace: true })}
                >
                    返回首頁
                </button>
            </div>
        </div>
    )
}
