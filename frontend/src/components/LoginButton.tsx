/**
 * LINE 登入按鈕元件
 * 未登入時顯示 LINE 綠色登入按鈕，已登入時顯示頭貼與暱稱
 */
import { useAuth } from '../hooks/useAuth'
import { Link } from 'react-router-dom'
import { LogOut } from 'lucide-react'
import './LoginButton.css'

export default function LoginButton() {
    const { user, isLoggedIn, loginWithLine, logout, loading } = useAuth()

    if (loading) return null

    if (isLoggedIn && user) {
        return (
            <div className="login-btn__user">
                <Link to="/profile" style={{ display: 'flex', alignItems: 'center', textDecoration: 'none', color: 'inherit' }}>
                    <img
                        className="login-btn__avatar"
                        src={user.pictureUrl || '/default-avatar.png'}
                        alt={user.customNickname}
                        onError={(e) => {
                            (e.target as HTMLImageElement).src = '/default-avatar.png'
                        }}
                    />
                </Link>
                <div className="login-btn__info">
                    <Link to="/profile" className="login-btn__name" style={{ textDecoration: 'none', color: 'inherit' }} title="查看個人積分中心">
                        {user.customNickname || user.displayName}
                    </Link>
                    <Link to="/levels" className="login-btn__level" style={{ textDecoration: 'none', color: 'inherit' }} title="查看等級權限規則">
                        Lv.{user.karmaLevel} {user.levelTitle}
                    </Link>
                </div>
                <button className="login-btn__logout" onClick={logout} title="登出">
                    <LogOut size={16} />
                </button>
            </div>
        )
    }

    return (
        <button className="login-btn__line" onClick={loginWithLine}>
            <svg className="login-btn__line-icon" viewBox="0 0 24 24" width="20" height="20">
                <path fill="#fff" d="M12 2C6.48 2 2 5.83 2 10.5c0 4.17 3.68 7.67 8.65 8.34.34.07.8.22.91.5.1.26.07.66.03.92l-.15.93c-.04.27-.2 1.05.93.57s6.15-3.62 8.39-6.2C22.57 13.53 22 12.08 22 10.5 22 5.83 17.52 2 12 2zm-3.09 11.03h-2.2a.44.44 0 0 1-.44-.44V8.44c0-.24.2-.44.44-.44.24 0 .44.2.44.44v3.71h1.76c.24 0 .44.2.44.44a.44.44 0 0 1-.44.44zm1.12-.44a.44.44 0 0 1-.88 0V8.44a.44.44 0 0 1 .88 0v4.15zm3.52 0a.44.44 0 0 1-.77.29l-2.13-2.9v2.61a.44.44 0 0 1-.88 0V8.44a.44.44 0 0 1 .78-.29l2.12 2.9V8.44a.44.44 0 0 1 .88 0v4.15zm3.07-3.27a.44.44 0 1 1 0 .88h-1.76v.83h1.76a.44.44 0 1 1 0 .88h-2.2a.44.44 0 0 1-.44-.44V8.44c0-.24.2-.44.44-.44h2.2a.44.44 0 1 1 0 .88h-1.76v.83h1.76z" />
            </svg>
            LINE 登入
        </button>
    )
}
