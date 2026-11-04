/**
 * 店家公開頁
 * 路由：/store/:id
 * 每間店都有：基本資訊、設施、頭獎紀錄、玩家中獎回報、評分評論、庫存
 * PRO 店另外顯示 Banner、公告、簡介、聯絡方式、中獎牆、相簿與含圖庫存
 */
import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
    MapPin, Phone, Clock, Navigation,
    ChevronLeft, ChevronRight, Store, Award, Image as ImageIcon,
    Package, Snowflake, Wifi, Accessibility, CreditCard, BookOpen,
    Hash, Maximize, Glasses, Newspaper, Tv, Armchair, Bath,
    Trophy, Star, PartyPopper
} from 'lucide-react'
import SeoHead from '../components/SeoHead'
import { fetchStorePage, fetchStorePublic, type StorePublicData } from '../hooks/api'
import './StorePage.css'

/** 設施標籤圖示（以後端回傳的中文標籤對應） */
const FACILITY_ICONS: Record<string, React.ReactNode> = {
    '冷氣': <Snowflake size={16} />,
    '廁所': <Bath size={16} />,
    '座位': <Armchair size={16} />,
    'Wi-Fi': <Wifi size={16} />,
    '無障礙空間': <Accessibility size={16} />,
    '電子支付': <CreditCard size={16} />,
    '提供攻略': <BookOpen size={16} />,
    '挑號服務': <Hash size={16} />,
    '專業刮板': <Package size={16} />,
    '放大鏡': <Maximize size={16} />,
    '老花眼鏡': <Glasses size={16} />,
    '明牌報紙': <Newspaper size={16} />,
    '運彩轉播': <Tv size={16} />,
}

/** R2 圖片 fallback：自訂域名失敗時改用 R2 dev 公開網址 */
const R2_CUSTOM = 'https://img.i168.win'
const R2_FALLBACK = 'https://pub-21021f943b5f4eb08695467bc899d993.r2.dev'

function imgFallback(e: React.SyntheticEvent<HTMLImageElement>) {
    const img = e.currentTarget
    if (img.src.includes(R2_CUSTOM)) {
        img.src = img.src.replace(R2_CUSTOM, R2_FALLBACK)
    }
}

/** 庫存狀態文字顏色 */
function statusColor(status: string) {
    if (status === '充足') return 'var(--sp-green)'
    if (status === '少量') return 'var(--sp-orange)'
    if (status === '售完' || status === '完售') return 'var(--sp-red)'
    return 'var(--sp-muted)'
}

/** ISO 時間 → YYYY/MM/DD */
function formatDate(iso: string | null) {
    if (!iso) return ''
    const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`)
    return `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`
}

/** PRO 專屬頁 API（/api/store/{id}）用到的欄位 */
interface ProPhoto { id: number; imageUrl: string; caption?: string }
interface ProInventoryItem { id: number; itemName: string; itemPrice: number; status: string; imageUrl?: string }
interface ProStoreData {
    store: {
        bannerUrl?: string
        announcement?: string
        description?: string
        businessHours?: string
        contactPhone?: string
        contactLine?: string
        contactFb?: string
    }
    winningWall?: ProPhoto[]
    gallery?: ProPhoto[]
    inventory?: ProInventoryItem[]
}

/** 可被收錄的門檻，需與後端 GET /api/stores/indexable 一致 */
const INDEXABLE_MIN_WIN_REPORTS = 3

function isIndexable(d: StorePublicData) {
    return d.isActive && (d.jackpots.count > 0 || d.ratings.totalCount > 0
        || d.winReports.count >= INDEXABLE_MIN_WIN_REPORTS || d.isPro)
}

/** LocalBusiness 結構化資料（與 scripts/generate-store-pages.mjs 的 buildJsonLd 一致） */
function buildJsonLd(d: StorePublicData): Record<string, unknown> {
    const ld: Record<string, unknown> = {
        '@context': 'https://schema.org',
        '@type': 'LocalBusiness',
        name: d.name,
        url: `https://i168.win/store/${d.id}`,
        address: {
            '@type': 'PostalAddress',
            streetAddress: d.address,
            addressLocality: d.district || undefined,
            addressRegion: d.city || undefined,
            addressCountry: 'TW',
        },
    }
    if (d.lat && d.lng) ld.geo = { '@type': 'GeoCoordinates', latitude: d.lat, longitude: d.lng }
    if (d.ratings.totalCount > 0) {
        ld.aggregateRating = {
            '@type': 'AggregateRating',
            ratingValue: d.ratings.avgRating,
            reviewCount: d.ratings.totalCount,
            bestRating: 5,
            worstRating: 1,
        }
    }
    return ld
}

function Stars({ value }: { value: number }) {
    return (
        <span className="sp-stars" aria-label={`${value} 顆星`}>
            {[1, 2, 3, 4, 5].map(n => (
                <Star key={n} size={14} fill={n <= Math.round(value) ? 'currentColor' : 'none'} />
            ))}
        </span>
    )
}

export default function StorePage() {
    const { id } = useParams<{ id: string }>()
    const [data, setData] = useState<StorePublicData | null>(null)
    // PRO 專屬內容（/api/store/{id}），抓不到不影響一般區塊
    const [pro, setPro] = useState<ProStoreData | null>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState('')
    const carouselRef = useRef<HTMLDivElement>(null)
    const heroRef = useRef<HTMLElement>(null)
    const jsonLd = useMemo(() => (data ? buildJsonLd(data) : undefined), [data])

    useEffect(() => {
        let cancelled = false
        async function load() {
            try {
                setLoading(true)
                setError('')
                setPro(null)
                const res = await fetchStorePublic(Number(id))
                if (cancelled) return
                setData(res)
                if (res.isPro) {
                    fetchStorePage(Number(id))
                        .then(p => { if (!cancelled) setPro(p) })
                        .catch(() => { /* PRO 內容抓不到就只顯示一般區塊 */ })
                }
            } catch (err: unknown) {
                const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                if (!cancelled) setError(detail || '無法載入此店家頁面')
            } finally {
                if (!cancelled) setLoading(false)
            }
        }
        if (id) load()
        return () => { cancelled = true }
    }, [id])

    // Banner 圖片 fallback
    useEffect(() => {
        const bannerUrl: string | undefined = pro?.store?.bannerUrl
        if (!bannerUrl || !bannerUrl.includes(R2_CUSTOM)) return
        const img = new Image()
        img.src = bannerUrl
        img.onerror = () => {
            if (heroRef.current) {
                heroRef.current.style.backgroundImage = `url(${bannerUrl.replace(R2_CUSTOM, R2_FALLBACK)})`
            }
        }
    }, [pro])

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
                <h2>找不到這間店家</h2>
                <p>{error}</p>
                <Link to="/map" className="sp-back-link">← 返回中獎地圖</Link>
            </div>
        )
    }

    const proStore = pro?.store
    const winningWall: ProPhoto[] = pro?.winningWall || []
    const gallery: ProPhoto[] = pro?.gallery || []
    const proInventory: ProInventoryItem[] = pro?.inventory || []
    const { jackpots, ratings, winReports, inventory } = data

    /** Google Maps 導航連結 */
    const googleMapUrl = data.lat && data.lng
        ? `https://www.google.com/maps/dir/?api=1&destination=${data.lat},${data.lng}`
        : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(data.address)}`

    /** 中獎牆輪播滑動 */
    const scrollCarousel = (dir: 'left' | 'right') => {
        if (!carouselRef.current) return
        const w = carouselRef.current.offsetWidth
        carouselRef.current.scrollBy({ left: dir === 'left' ? -w * 0.8 : w * 0.8, behavior: 'smooth' })
    }

    const summaryParts = [
        jackpots.count > 0 ? `開出 ${jackpots.count} 次頭獎` : '',
        ratings.totalCount > 0 ? `評分 ${ratings.avgRating}（${ratings.totalCount} 則）` : '',
        winReports.count > 0 ? `近 ${winReports.windowDays} 天玩家回報中獎 ${winReports.count} 次` : '',
    ].filter(Boolean)
    const seoDescription = proStore?.description
        || `${data.name}，位於${data.address}。${summaryParts.join('、') || '查看頭獎紀錄、玩家評分、中獎回報與庫存。'}`

    let delay = 0.05
    const nextDelay = () => (delay += 0.05)

    return (
        <div className="store-page">
            <SeoHead
                title={`${data.name}｜頭獎紀錄與評價`}
                description={seoDescription}
                path={`/store/${data.id}`}
                jsonLd={jsonLd}
                noindex={!isIndexable(data)}
            />

            {/* === Hero === */}
            <section
                ref={heroRef}
                className="sp-hero"
                style={proStore?.bannerUrl ? { backgroundImage: `url(${proStore.bannerUrl})` } : {}}
            >
                <div className="sp-hero__overlay" />
                <motion.div
                    className="sp-hero__content"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    <h1 className="sp-hero__name">{data.name}</h1>
                    <p className="sp-hero__address">
                        <MapPin size={16} /> {data.address}
                    </p>
                    <div className="sp-hero__badges">
                        {jackpots.count > 0 && (
                            <span className="sp-badge sp-badge--jackpot"><Trophy size={14} /> 頭獎 {jackpots.count} 次</span>
                        )}
                        {ratings.totalCount > 0 && (
                            <span className="sp-badge"><Star size={14} /> {ratings.avgRating}（{ratings.totalCount}）</span>
                        )}
                        {data.isPro && <span className="sp-badge sp-badge--pro">👑 PRO 店家</span>}
                        {!data.isActive && <span className="sp-badge">已停業</span>}
                    </div>
                    {proStore?.announcement && (
                        <div className="sp-hero__announcement">📢 {proStore.announcement}</div>
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
                    {proStore?.contactPhone && (
                        <a href={`tel:${proStore.contactPhone}`} className="sp-action-btn sp-action-btn--phone">
                            <Phone size={18} /> 撥打電話
                        </a>
                    )}
                    {proStore?.contactLine && (
                        <a href={proStore.contactLine.startsWith('http') ? proStore.contactLine : `https://line.me/ti/p/${proStore.contactLine}`} target="_blank" rel="noopener noreferrer" className="sp-action-btn sp-action-btn--line">
                            LINE
                        </a>
                    )}
                    {proStore?.contactFb && (
                        <a href={proStore.contactFb} target="_blank" rel="noopener noreferrer" className="sp-action-btn sp-action-btn--fb">
                            Facebook
                        </a>
                    )}
                </div>

                {/* 未認領：邀請店家認領 */}
                {!data.isClaimed && (
                    <div className="sp-claim-cta glass-card">
                        <span>這是你的店嗎？認領後可以更新庫存、回覆玩家。</span>
                        <Link to={`/merchant/claim/${data.id}`} className="sp-claim-cta__btn">免費認領</Link>
                    </div>
                )}

                {/* 店家簡介（PRO） */}
                {(proStore?.description || proStore?.businessHours) && (
                    <motion.section className="sp-section glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: nextDelay() }}>
                        <h2 className="sp-section__title"><Store size={20} /> 關於我們</h2>
                        {proStore.description && <p className="sp-description">{proStore.description}</p>}
                        {proStore.businessHours && (
                            <div className="sp-business-hours">
                                <Clock size={16} /> {proStore.businessHours}
                            </div>
                        )}
                    </motion.section>
                )}

                {/* 頭獎紀錄 */}
                <motion.section className="sp-section glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: nextDelay() }}>
                    <h2 className="sp-section__title"><Trophy size={20} /> 頭獎紀錄</h2>
                    {jackpots.items.length > 0 ? (
                        <ul className="sp-list">
                            {jackpots.items.map(j => (
                                <li key={`${j.gameType}-${j.period}`} className="sp-list__row">
                                    <span className="sp-list__main">{j.gameType}</span>
                                    <span className="sp-list__sub">第 {j.period} 期</span>
                                    <span className="sp-list__date">{j.drawDate}</span>
                                </li>
                            ))}
                        </ul>
                    ) : (
                        <p className="sp-empty">目前沒有台彩公告的頭獎紀錄。</p>
                    )}
                </motion.section>

                {/* 玩家中獎回報 */}
                <motion.section className="sp-section glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: nextDelay() }}>
                    <h2 className="sp-section__title"><PartyPopper size={20} /> 玩家中獎回報</h2>
                    {winReports.count > 0 ? (
                        <>
                            <p className="sp-stat-line">
                                近 {winReports.windowDays} 天共 <strong>{winReports.count}</strong> 則，
                                合計 <strong>${winReports.totalAmount.toLocaleString()}</strong>
                            </p>
                            <ul className="sp-list">
                                {winReports.recent.map((w, i) => (
                                    <li key={i} className="sp-list__row">
                                        <span className="sp-list__main">${w.amount.toLocaleString()}</span>
                                        <span className="sp-list__sub">{w.gameName || '未填款式'}</span>
                                        <span className="sp-list__date">{formatDate(w.createdAt)}</span>
                                    </li>
                                ))}
                            </ul>
                        </>
                    ) : (
                        <p className="sp-empty">還沒有玩家回報在這裡中獎。</p>
                    )}
                    <Link to="/map" className="sp-inline-link">在這裡中獎了？到地圖回報 →</Link>
                </motion.section>

                {/* 評分與評論 */}
                <motion.section className="sp-section glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: nextDelay() }}>
                    <h2 className="sp-section__title"><Star size={20} /> 玩家評價</h2>
                    {ratings.totalCount > 0 ? (
                        <>
                            <div className="sp-rating-summary">
                                <span className="sp-rating-summary__score">{ratings.avgRating}</span>
                                <Stars value={ratings.avgRating} />
                                <span className="sp-list__sub">{ratings.totalCount} 則評分</span>
                            </div>
                            {Object.keys(ratings.serviceTagStats).length > 0 && (
                                <div className="sp-facilities">
                                    {Object.entries(ratings.serviceTagStats)
                                        .sort((a, b) => b[1] - a[1])
                                        .map(([tag, n]) => (
                                            <span key={tag} className="sp-facility-tag">{tag} × {n}</span>
                                        ))}
                                </div>
                            )}
                            <ul className="sp-reviews">
                                {ratings.recent.map((r, i) => (
                                    <li key={i} className="sp-review">
                                        <div className="sp-review__head">
                                            <strong>{r.userName}</strong>
                                            <span className="sp-list__sub">Lv.{r.userLevel}</span>
                                            {r.isGpsVerified && <span className="sp-list__sub">📍 現場評分</span>}
                                            <Stars value={r.rating} />
                                            <span className="sp-list__date">{formatDate(r.createdAt)}</span>
                                        </div>
                                        {r.comment && <p className="sp-review__comment">{r.comment}</p>}
                                    </li>
                                ))}
                            </ul>
                        </>
                    ) : (
                        <p className="sp-empty">還沒有玩家評分。</p>
                    )}
                    <Link to="/map" className="sp-inline-link">去過這間店？到地圖評分 →</Link>
                </motion.section>

                {/* 設施標籤 */}
                {data.facilities.length > 0 && (
                    <motion.section className="sp-section glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: nextDelay() }}>
                        <h2 className="sp-section__title">🏗️ 店內設施</h2>
                        <div className="sp-facilities">
                            {data.facilities.map(label => (
                                <span key={label} className="sp-facility-tag">
                                    {FACILITY_ICONS[label]} {label}
                                </span>
                            ))}
                        </div>
                    </motion.section>
                )}

                {/* 中獎牆輪播（PRO） */}
                {winningWall.length > 0 && (
                    <motion.section className="sp-section glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: nextDelay() }}>
                        <h2 className="sp-section__title"><Award size={20} /> 中獎牆</h2>
                        <div className="sp-carousel-wrapper">
                            <button className="sp-carousel-btn sp-carousel-btn--left" onClick={() => scrollCarousel('left')}>
                                <ChevronLeft size={20} />
                            </button>
                            <div className="sp-carousel" ref={carouselRef}>
                                {winningWall.map((photo) => (
                                    <div key={photo.id} className="sp-carousel-card">
                                        <img src={photo.imageUrl} alt={photo.caption || '中獎照片'} loading="lazy" onError={imgFallback} />
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

                {/* 店內相簿（PRO） */}
                {gallery.length > 0 && (
                    <motion.section className="sp-section glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: nextDelay() }}>
                        <h2 className="sp-section__title"><ImageIcon size={20} /> 店內環境</h2>
                        <div className="sp-gallery">
                            {gallery.map((photo) => (
                                <div key={photo.id} className="sp-gallery-item">
                                    <img src={photo.imageUrl} alt={photo.caption || '店內照片'} loading="lazy" onError={imgFallback} />
                                    {photo.caption && <p className="sp-gallery-caption">{photo.caption}</p>}
                                </div>
                            ))}
                        </div>
                    </motion.section>
                )}

                {/* 庫存：PRO 用含圖的官方庫存，其他店用公開資料 */}
                {(proInventory.length > 0 || inventory.official.length > 0 || inventory.community.length > 0) && (
                    <motion.section className="sp-section glass-card" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: nextDelay() }}>
                        <h2 className="sp-section__title"><Package size={20} /> 庫存</h2>
                        {proInventory.length > 0 ? (
                            <div className="sp-inventory">
                                {proInventory.map((inv) => (
                                    <div key={inv.id} className="sp-inventory-card">
                                        {inv.imageUrl && <img src={inv.imageUrl} alt={inv.itemName} className="sp-inventory-img" loading="lazy" onError={imgFallback} />}
                                        <div className="sp-inventory-info">
                                            <span className="sp-inventory-name">{inv.itemName}</span>
                                            {inv.itemPrice > 0 && <span className="sp-inventory-price">NT${inv.itemPrice}</span>}
                                        </div>
                                        <span className="sp-inventory-status" style={{ color: statusColor(inv.status) }}>{inv.status}</span>
                                    </div>
                                ))}
                            </div>
                        ) : inventory.official.length > 0 && (
                            <>
                                <h3 className="sp-subtitle">店家公布</h3>
                                <div className="sp-inventory">
                                    {inventory.official.map(inv => (
                                        <div key={inv.itemName} className="sp-inventory-card">
                                            <div className="sp-inventory-info">
                                                <span className="sp-inventory-name">{inv.itemName}</span>
                                                {inv.itemPrice > 0 && <span className="sp-inventory-price">NT${inv.itemPrice}</span>}
                                            </div>
                                            <span className="sp-inventory-status" style={{ color: statusColor(inv.status) }}>{inv.status}</span>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
                        {inventory.community.length > 0 && (
                            <>
                                <h3 className="sp-subtitle">玩家回報（7 天內）</h3>
                                <div className="sp-inventory">
                                    {inventory.community.map(inv => (
                                        <div key={inv.item} className="sp-inventory-card">
                                            <div className="sp-inventory-info">
                                                <span className="sp-inventory-name">{inv.item}</span>
                                                <span className="sp-inventory-price">{formatDate(inv.updatedAt)}</span>
                                            </div>
                                            <span className="sp-inventory-status" style={{ color: statusColor(inv.status) }}>{inv.status}</span>
                                        </div>
                                    ))}
                                </div>
                            </>
                        )}
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
