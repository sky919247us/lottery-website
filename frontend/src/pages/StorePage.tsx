/**
 * 商家專屬頁面 — 公開展示
 * 路由：/store/:id
 * PRO 商家的對外展示門面，包含 Banner、簡介、中獎牆、相簿、庫存與設施標籤
 */
import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
    MapPin, Phone, Clock, Navigation,
    ChevronLeft, ChevronRight, Store, Award, Image as ImageIcon,
    Package, Snowflake, Wifi, Accessibility, CreditCard, BookOpen,
    Hash, Maximize, Glasses, Newspaper, Tv, Armchair, Bath
} from 'lucide-react'
import SeoHead from '../components/SeoHead'
import { fetchStorePage } from '../hooks/api'
import './StorePage.css'

/** 設施標籤對應表 */
const FACILITY_MAP: Record<string, { label: string; icon: React.ReactNode }> = {
    hasAC: { label: '冷氣', icon: <Snowflake size={16} /> },
    hasToilet: { label: '廁所', icon: <Bath size={16} /> },
    hasSeats: { label: '座位', icon: <Armchair size={16} /> },
    hasWifi: { label: 'Wi-Fi', icon: <Wifi size={16} /> },
    hasAccessibility: { label: '無障礙', icon: <Accessibility size={16} /> },
    hasEPay: { label: '電子支付', icon: <CreditCard size={16} /> },
    hasStrategy: { label: '攻略', icon: <BookOpen size={16} /> },
    hasNumberPick: { label: '挑號服務', icon: <Hash size={16} /> },
    hasScratchBoard: { label: '專業刮板', icon: <Package size={16} /> },
    hasMagnifier: { label: '放大鏡', icon: <Maximize size={16} /> },
    hasReadingGlasses: { label: '老花眼鏡', icon: <Glasses size={16} /> },
    hasNewspaper: { label: '明牌報紙', icon: <Newspaper size={16} /> },
    hasSportTV: { label: '運彩轉播', icon: <Tv size={16} /> },
}

/** 庫存狀態文字顏色 */
function statusColor(status: string) {
    if (status === '充足') return 'var(--sp-green)'
    if (status === '少量') return 'var(--sp-orange)'
    if (status === '售完') return 'var(--sp-red)'
    return 'var(--sp-muted)'
}

export default function StorePage() {
    const { id } = useParams<{ id: string }>()
    const [data, setData] = useState<any>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const carouselRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        async function load() {
            try {
                setLoading(true)
                const res = await fetchStorePage(Number(id))
                setData(res)
            } catch (err: any) {
                setError(err?.response?.data?.detail || '無法載入此店家頁面')
            } finally {
                setLoading(false)
            }
        }
        if (id) load()
    }, [id])

    if (loading) {
        return (
            <div className="sp-loading">
                <div className="spinner" />
                <p>載入店家頁面中...</p>
            </div>
        )
    }

    if (error || !data) {
        return (
            <div className="sp-error">
                <Store size={48} />
                <h2>此店家尚未開通專屬頁面</h2>
                <p>{error}</p>
                <Link to="/map" className="sp-back-link">← 返回中獎地圖</Link>
            </div>
        )
    }

    const { store, facilities, gallery, winningWall, inventory } = data
    const activeFacilities = Object.entries(facilities).filter(([, v]) => v)

    /** Google Maps 導航連結 */
    const googleMapUrl = store.lat && store.lng
        ? `https://www.google.com/maps/dir/?api=1&destination=${store.lat},${store.lng}`
        : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(store.address)}`

    /** 中獎牆輪播滑動 */
    const scrollCarousel = (dir: 'left' | 'right') => {
        if (!carouselRef.current) return
        const w = carouselRef.current.offsetWidth
        carouselRef.current.scrollBy({ left: dir === 'left' ? -w * 0.8 : w * 0.8, behavior: 'smooth' })
    }

    return (
        <div className="store-page">
            <SeoHead
                title={`${store.name} — 刮刮研究室`}
                description={store.description || `${store.name}，位於${store.address}。查看庫存、設施與中獎牆。`}
                path={`/store/${id}`}
            />

            {/* === Hero Banner === */}
            <section className="sp-hero" style={store.bannerUrl ? { backgroundImage: `url(${store.bannerUrl})` } : {}}>
                <div className="sp-hero__overlay" />
                <motion.div
                    className="sp-hero__content"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    <h1 className="sp-hero__name">{store.name}</h1>
                    <p className="sp-hero__address">
                        <MapPin size={16} /> {store.address}
                    </p>
                    {store.announcement && (
                        <div className="sp-hero__announcement">📢 {store.announcement}</div>
                    )}
                </motion.div>
            </section>

            {/* === 主要內容 === */}
            <div className="sp-container">
                {/* 快速操作列 */}
                <div className="sp-actions">
                    <a href={googleMapUrl} target="_blank" rel="noopener noreferrer" className="sp-action-btn sp-action-btn--nav">
                        <Navigation size={18} /> 導航前往
                    </a>
                    {store.contactPhone && (
                        <a href={`tel:${store.contactPhone}`} className="sp-action-btn sp-action-btn--phone">
                            <Phone size={18} /> 撥打電話
                        </a>
                    )}
                    {store.contactLine && (
                        <a href={store.contactLine.startsWith('http') ? store.contactLine : `https://line.me/ti/p/${store.contactLine}`} target="_blank" rel="noopener noreferrer" className="sp-action-btn sp-action-btn--line">
                            LINE
                        </a>
                    )}
                    {store.contactFb && (
                        <a href={store.contactFb} target="_blank" rel="noopener noreferrer" className="sp-action-btn sp-action-btn--fb">
                            Facebook
                        </a>
                    )}
                </div>

                {/* 店家簡介 */}
                {(store.description || store.businessHours) && (
                    <motion.section
                        className="sp-section glass-card"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.1 }}
                    >
                        <h2 className="sp-section__title"><Store size={20} /> 關於我們</h2>
                        {store.description && <p className="sp-description">{store.description}</p>}
                        {store.businessHours && (
                            <div className="sp-business-hours">
                                <Clock size={16} /> {store.businessHours}
                            </div>
                        )}
                    </motion.section>
                )}

                {/* 設施標籤 */}
                {activeFacilities.length > 0 && (
                    <motion.section
                        className="sp-section glass-card"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.15 }}
                    >
                        <h2 className="sp-section__title">🏗️ 店內設施</h2>
                        <div className="sp-facilities">
                            {activeFacilities.map(([key]) => {
                                const f = FACILITY_MAP[key]
                                if (!f) return null
                                return (
                                    <span key={key} className="sp-facility-tag">
                                        {f.icon} {f.label}
                                    </span>
                                )
                            })}
                        </div>
                    </motion.section>
                )}

                {/* 中獎牆輪播 */}
                {winningWall.length > 0 && (
                    <motion.section
                        className="sp-section glass-card"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 }}
                    >
                        <h2 className="sp-section__title"><Award size={20} /> 中獎牆</h2>
                        <div className="sp-carousel-wrapper">
                            <button className="sp-carousel-btn sp-carousel-btn--left" onClick={() => scrollCarousel('left')}>
                                <ChevronLeft size={20} />
                            </button>
                            <div className="sp-carousel" ref={carouselRef}>
                                {winningWall.map((photo: any) => (
                                    <div key={photo.id} className="sp-carousel-card">
                                        <img src={photo.imageUrl} alt={photo.caption || '中獎照片'} loading="lazy" />
                                        {photo.caption && <p className="sp-carousel-caption">{photo.caption}</p>}
                                    </div>
                                ))}
                            </div>
                            <button className="sp-carousel-btn sp-carousel-btn--right" onClick={() => scrollCarousel('right')}>
                                <ChevronRight size={20} />
                            </button>
                        </div>
                    </motion.section>
                )}

                {/* 店內相簿 */}
                {gallery.length > 0 && (
                    <motion.section
                        className="sp-section glass-card"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.25 }}
                    >
                        <h2 className="sp-section__title"><ImageIcon size={20} /> 店內環境</h2>
                        <div className="sp-gallery">
                            {gallery.map((photo: any) => (
                                <div key={photo.id} className="sp-gallery-item">
                                    <img src={photo.imageUrl} alt={photo.caption || '店內照片'} loading="lazy" />
                                    {photo.caption && <p className="sp-gallery-caption">{photo.caption}</p>}
                                </div>
                            ))}
                        </div>
                    </motion.section>
                )}

                {/* 即時庫存 */}
                {inventory.length > 0 && (
                    <motion.section
                        className="sp-section glass-card"
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.3 }}
                    >
                        <h2 className="sp-section__title"><Package size={20} /> 即時庫存</h2>
                        <div className="sp-inventory">
                            {inventory.map((inv: any) => (
                                <div key={inv.id} className="sp-inventory-card">
                                    {inv.imageUrl && <img src={inv.imageUrl} alt={inv.itemName} className="sp-inventory-img" loading="lazy" />}
                                    <div className="sp-inventory-info">
                                        <span className="sp-inventory-name">{inv.itemName}</span>
                                        {inv.itemPrice > 0 && <span className="sp-inventory-price">NT${inv.itemPrice}</span>}
                                    </div>
                                    <span className="sp-inventory-status" style={{ color: statusColor(inv.status) }}>
                                        {inv.status}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </motion.section>
                )}

                {/* 返回地圖 */}
                <div className="sp-footer">
                    <Link to="/map" className="sp-back-link">← 返回中獎地圖</Link>
                </div>
            </div>
        </div>
    )
}
