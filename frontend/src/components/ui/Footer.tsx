/**
 * Footer 底部元件
 */
import { Heart } from 'lucide-react'
import { Link } from 'react-router-dom'
import './Footer.css'

export default function Footer() {
    return (
        <footer className="footer">
            <div className="container footer__inner">
                <p className="footer__text">
                    <Heart size={14} className="footer__heart" />
                    刮刮研究室 — 僅供資訊參考，不構成投資建議
                </p>
                <nav className="footer__links">
                    <Link to="/contact" className="footer__link">聯絡我們</Link>
                    <span className="footer__sep">·</span>
                    <Link to="/refund-policy" className="footer__link">退換貨政策</Link>
                    <span className="footer__sep">·</span>
                    <Link to="/delivery-policy" className="footer__link">商品交付政策</Link>
                </nav>
                <p className="footer__sub">
                    資料來源：台灣彩券官方網站 | © {new Date().getFullYear()}
                </p>
            </div>
        </footer>
    )
}
