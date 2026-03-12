/**
 * MobileTabBar 行動版底部導覽列
 * 僅在手機寬度（≤768px）時顯示，提供快速頁面切換
 */
import { Link, useLocation } from 'react-router-dom'
import { Home, Film, Calculator, User } from 'lucide-react'
import './MobileTabBar.css'

/** 底部導覽項目定義 */
const TAB_ITEMS = [
    { to: '/', label: '首頁', icon: Home },
    { to: '/videos', label: '影片', icon: Film },
    { to: '/calculator', label: '計算機', icon: Calculator },
    { to: '/wallet', label: '我的', icon: User },
]

export default function MobileTabBar() {
    const location = useLocation()

    return (
        <nav className="mobile-tab-bar" aria-label="行動版導覽">
            {TAB_ITEMS.map((item) => {
                const Icon = item.icon
                const isActive = location.pathname === item.to
                return (
                    <Link
                        key={item.to}
                        to={item.to}
                        className={`mobile-tab-bar__item ${isActive ? 'mobile-tab-bar__item--active' : ''}`}
                    >
                        <Icon size={22} strokeWidth={isActive ? 2.2 : 1.8} />
                        <span>{item.label}</span>
                    </Link>
                )
            })}
        </nav>
    )
}
