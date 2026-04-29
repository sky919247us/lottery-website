/**
 * Footer 底部元件
 */
import { Heart } from 'lucide-react'
import './Footer.css'

export default function Footer() {
    return (
        <footer className="footer">
            <div className="container footer__inner">
                <p className="footer__text">
                    <Heart size={14} className="footer__heart" />
                    刮刮研究室 — 僅供資訊參考，不構成投資建議
                </p>
                <p className="footer__sub">
                    資料來源：台灣彩券官方網站 | © {new Date().getFullYear()}
                </p>
            </div>
        </footer>
    )
}
