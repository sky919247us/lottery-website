/**
 * NavBar 導覽列元件
 * Apple Style 固定頂部導覽
 */
import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Menu, X, Sparkles } from 'lucide-react'
import LoginButton from '../LoginButton'
import './NavBar.css'

/** 導覽連結定義 */
type NavLink = { to: string; label: string; icon: React.ReactNode | null; external?: boolean };
const NAV_LINKS: NavLink[] = [
  { to: '/', label: '首頁', icon: null },
  { to: '/videos', label: '影片列表', icon: null },
  { to: '/calculator', label: '計算機', icon: null },
  { to: '/wallet', label: '我的錢包', icon: null },
  { to: '/map', label: '中獎地圖', icon: null },
  { to: 'https://bingo.i168.win/', label: '賓果研究室', icon: null, external: true },
]

export default function NavBar() {
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <nav className="navbar">
      <div className="navbar__inner container">
        <Link to="/" className="navbar__logo">
          <Sparkles size={20} />
          <span>刮刮研究室</span>
        </Link>

        <ul className={`navbar__links ${menuOpen ? 'navbar__links--open' : ''}`}>
          {NAV_LINKS.map((link) => (
            <li key={link.to}>
              {link.external ? (
                <a
                  href={link.to}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="navbar__link"
                  onClick={() => setMenuOpen(false)}
                >
                  {link.icon || link.label}
                </a>
              ) : (
                <Link
                  to={link.to}
                  className={`navbar__link ${location.pathname === link.to ? 'navbar__link--active' : ''}`}
                  onClick={() => setMenuOpen(false)}
                >
                  {link.icon || link.label}
                </Link>
              )}
            </li>
          ))}
        </ul>

        <div className="navbar__actions">
          <LoginButton />
          <button
            className="navbar__toggle"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="切換選單"
          >
            {menuOpen ? <X size={24} /> : <Menu size={24} />}
          </button>
        </div>
      </div>
    </nav>
  )
}
