/**
 * 詳情頁 — 刮刮樂獎金結構、三大指標、獨家特色與殘值計算機
 */
import { useEffect, useState, useMemo } from 'react'
import { useParams, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
    ArrowLeft, Calculator, Trophy, Calendar, DollarSign,
    TrendingUp, Share2, Percent, Target, Sparkles, Play,
    MapPin, Store, Navigation, AlertTriangle
} from 'lucide-react'
import {
    fetchScratchcardDetail, fetchNearbyStock, recordRetailerExposure,
    type ScratchcardDetail as DetailType, type NearbyStockStore
} from '../hooks/api'
import SeoHead from '../components/SeoHead'
import './Detail.css'

/** YouTube 新品實測播放清單 ID */
const REVIEW_PLAYLIST_ID = 'PLBdL0u1z-6I5Psfqk72nmPKhZ_UESHDK-'

/** 面額 → 每本張數對照表 */
const PRICE_TO_TICKETS_PER_BOOK: Record<number, number> = {
    100: 100,
    200: 100,
    300: 100,
    500: 50,
    1000: 25,
    2000: 19,
}

/** 根據面額取得預設每本張數 */
function getDefaultTicketsPerBook(price: number): number {
    return PRICE_TO_TICKETS_PER_BOOK[price] || 100
}

export default function Detail() {
    const { id } = useParams<{ id: string }>()
    const [detail, setDetail] = useState<DetailType | null>(null)
    const [loading, setLoading] = useState(true)
    /** 每本張數（依面額自動設定） */
    const [ticketsPerBook, setTicketsPerBook] = useState(100)
    /** 各獎項已開出張數 */
    const [openedCounts, setOpenedCounts] = useState<Record<number, number>>({})
    /** 未中獎已開出張數 */
    const [openedZero, setOpenedZero] = useState(0)
    /** 實務返還率（拉桿調整） */
    const [practicalRate, setPracticalRate] = useState(60)

    // 附近有貨店家
    const [nearbyStores, setNearbyStores] = useState<NearbyStockStore[]>([])
    const [nearbyLoading, setNearbyLoading] = useState(false)
    const [showNearby, setShowNearby] = useState(false)

    useEffect(() => {
        if (id) {
            loadDetail(Number(id))
        }
    }, [id])

    async function loadDetail(scratchcardId: number) {
        try {
            const data = await fetchScratchcardDetail(scratchcardId)
            setDetail(data)
            // 依面額自動設定每本張數
            setTicketsPerBook(getDefaultTicketsPerBook(data.price))
        } catch {
            setDetail(null)
        } finally {
            setLoading(false)
        }
    }

    /** 載入附近有貨店家 */
    async function loadNearbyStores() {
        if (!detail) return
        setNearbyLoading(true)
        setShowNearby(true)
        try {
            // 嘗試取得使用者位置
            let lat: number | undefined
            let lng: number | undefined
            if (navigator.geolocation) {
                try {
                    const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
                        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
                    )
                    lat = pos.coords.latitude
                    lng = pos.coords.longitude
                } catch {
                    // GPS 失敗不阻止查詢
                }
            }
            const result = await fetchNearbyStock(detail.id, lat, lng)
            setNearbyStores(result.stores)

            // 紀錄曝光次數
            result.stores.forEach(store => {
                recordRetailerExposure(store.retailerId).catch(() => {})
            })
        } catch {
            setNearbyStores([])
        } finally {
            setNearbyLoading(false)
        }
    }

    /** 每本獎項分佈計算 */
    const bookAnalysis = useMemo(() => {
        if (!detail || !detail.prizes.length || detail.totalIssued === 0 || ticketsPerBook <= 0) return null

        const totalBooks = detail.totalIssued / ticketsPerBook
        if (totalBooks <= 0) return null

        const rows = detail.prizes.map((p, idx) => {
            const perBook = p.totalCount / totalBooks
            const opened = openedCounts[idx] || 0
            const remaining = Math.max(0, perBook - opened)
            return {
                prizeName: p.prizeName,
                prizeAmount: p.prizeAmount,
                totalCount: p.totalCount,
                perBook: perBook,
                opened,
                remaining,
            }
        })

        // 0 元獎項（未中獎張數）
        const prizeTickets = rows.reduce((s, r) => s + r.perBook, 0)
        const zeroTicketsPerBook = Math.max(0, ticketsPerBook - prizeTickets)
        const totalOpened = rows.reduce((s, r) => s + r.opened, 0) + openedZero

        // 殘值計算
        const remainingValue = rows.reduce((s, r) => s + r.remaining * r.prizeAmount, 0)
        const remainingTickets = ticketsPerBook - totalOpened
        const costRemaining = remainingTickets * detail.price

        // 返還率 = 總獎金 / 總成本（整本）
        const totalPrizePerBook = rows.reduce((s, r) => s + r.perBook * r.prizeAmount, 0)
        const totalCostPerBook = ticketsPerBook * detail.price
        const returnRate = totalCostPerBook > 0 ? Math.round((totalPrizePerBook / totalCostPerBook) * 1000) / 10 : 0

        // 實務調整係數：實務返還率 / 理論返還率
        const adjustRatio = returnRate > 0 ? practicalRate / returnRate : 1
        const adjustedRemainingValue = remainingValue * adjustRatio
        const adjustedTotalPrize = totalPrizePerBook * adjustRatio

        return {
            totalBooks, rows, zeroTicketsPerBook,
            remainingValue: adjustedRemainingValue,
            remainingTickets, costRemaining, totalOpened,
            returnRate,
            adjustedTotalPrize,
        }
    }, [detail, ticketsPerBook, openedCounts, openedZero, practicalRate])

    /** 更新某獎項已開出張數 */
    function updateOpened(idx: number, value: number) {
        setOpenedCounts(prev => ({ ...prev, [idx]: Math.max(0, value) }))
    }

    /** 計算回本率（ROI） */
    function calculateROI() {
        if (!detail || detail.totalIssued === 0) return 0
        const totalPrize = detail.prizes.reduce((sum, p) => sum + p.prizeAmount * p.totalCount, 0)
        const totalCost = detail.totalIssued * detail.price
        return totalCost > 0 ? Math.round((totalPrize / totalCost) * 100 * 10) / 10 : 0
    }

    /** 從 prizes 計算中獎率（有獎張數 / 總發行張數） */
    function computeWinRate(): number {
        if (!detail || detail.totalIssued === 0 || detail.prizes.length === 0) return 0
        const winningTickets = detail.prizes
            .filter(p => p.prizeAmount > 0)
            .reduce((sum, p) => sum + p.totalCount, 0)
        return Math.round((winningTickets / detail.totalIssued) * 10000) / 100
    }

    const roi = calculateROI()
    const winRate = computeWinRate()
    const winRateStr = winRate > 0 ? `${winRate}%` : (detail?.overallWinRate || '-')

    /** 獨家特色判定 */
    function getFeatures() {
        if (!detail) return []
        const features: { icon: React.ReactNode; title: string; desc: string }[] = []

        if (winRate > 49) {
            features.push({
                icon: <TrendingUp size={20} />,
                title: '高勝率',
                desc: `中獎率高達 ${winRateStr}`,
            })
        }

        if (roi > 70) {
            features.push({
                icon: <DollarSign size={20} />,
                title: '回本率高',
                desc: `ROI 高於平均${(roi - 65).toFixed(0)}%`,
            })
        }

        if (detail.grandPrizeUnclaimed > 0 && detail.grandPrizeCount > 0) {
            const ratio = Math.round((detail.grandPrizeUnclaimed / detail.grandPrizeCount) * 100)
            features.push({
                icon: <Trophy size={20} />,
                title: '頭獎仍在',
                desc: `頭獎剩餘${ratio}%尚未開出`,
            })
        }

        if (detail.price <= 200) {
            features.push({
                icon: <Target size={20} />,
                title: '小額入門',
                desc: `每張僅 $${detail.price}，適合小資族`,
            })
        }

        return features
    }

    if (loading) {
        return (
            <div className="detail__loading">
                <div className="spinner" />
                <p>載入中...</p>
            </div>
        )
    }

    if (!detail) {
        return (
            <div className="detail__loading">
                <p>找不到該刮刮樂</p>
                <Link to="/">返回首頁</Link>
            </div>
        )
    }

    const features = getFeatures()

    return (
        <div className="detail container">
            {/* 頂部導覽 */}
            <div className="detail__top-bar">
                <Link to="/" className="detail__back">
                    <ArrowLeft size={18} />
                    返回列表
                </Link>
                <button className="detail__share-btn" onClick={() => navigator.clipboard?.writeText(window.location.href)}>
                    <Share2 size={16} />
                </button>
            </div>

            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
            >
                <SeoHead
                    title={`${detail.name} — 中獎率 ${winRateStr} / 最高獎金 ${detail.maxPrize || ''}`}
                    description={`${detail.name} 中獎率 ${winRateStr}，最高獎金 ${detail.maxPrize || detail.maxPrizeAmount?.toLocaleString() + '元'}，售價 $${detail.price.toLocaleString()}。查看獎金結構、殘值計算與附近有貨店家。`}
                    path={`/detail/${detail.id}`}
                    jsonLd={{
                        '@context': 'https://schema.org',
                        '@type': 'Product',
                        name: detail.name,
                        description: `台灣彩券刮刮樂「${detail.name}」，售價 NT$${detail.price}，最高獎金 ${detail.maxPrize || ''}`,
                        offers: {
                            '@type': 'Offer',
                            price: detail.price,
                            priceCurrency: 'TWD',
                            availability: detail.salesRateValue >= 100 ? 'https://schema.org/SoldOut' : 'https://schema.org/InStock',
                        },
                    }}
                />
                {/* 標題區 */}
                <header className="detail__header glass-card">
                    <div className="detail__header-content">
                        <div>
                            <div className="detail__game-id">
                                {detail.isPreview
                                    ? <span className="detail__preview-badge">即將發售</span>
                                    : `NO. ${detail.gameId}`}
                            </div>
                            <h1 className="detail__title">{detail.name}</h1>
                        </div>
                        <div className="detail__tags">
                            <span className="detail__tag detail__tag--price">
                                <DollarSign size={14} />
                                NT$ {detail.price.toLocaleString()}
                            </span>
                            {detail.isHighWinRate || (detail.grandPrizeUnclaimed > 0 && detail.salesRateValue > 85) ? (
                                <span className="detail__tag detail__tag--alert">
                                    <AlertTriangle size={14} style={{ marginRight: '4px' }} />
                                    {detail.isHighWinRate ? '🔥 高勝率預警' : '💰 頭獎仍在'}
                                </span>
                            ) : null}
                        </div>
                    </div>
                </header>

                {/* 三大指標卡片 */}
                <div className="detail__metrics">
                    <div className="detail__metric glass-card">
                        <div className="detail__metric-icon">
                            <Percent size={18} />
                        </div>
                        <span className="detail__metric-label">中獎率</span>
                        <strong className="detail__metric-value">{winRateStr}</strong>
                    </div>
                    <div className="detail__metric glass-card detail__metric--highlight">
                        <div className="detail__metric-icon">
                            <TrendingUp size={18} />
                        </div>
                        <span className="detail__metric-label">回本率 (ROI)</span>
                        <strong className="detail__metric-value">{roi}%</strong>
                    </div>
                    <div className="detail__metric glass-card">
                        <div className="detail__metric-icon">
                            <Trophy size={18} />
                        </div>
                        <span className="detail__metric-label">頭獎金額</span>
                        <strong className="detail__metric-value">
                            {detail.maxPrize || `$${detail.maxPrizeAmount?.toLocaleString()}`}
                        </strong>
                    </div>
                </div>

                {/* 即獎剩餘數量 */}
                {detail.grandPrizeCount > 0 && (
                    <section className="detail__remaining glass-card">
                        <div className="detail__remaining-header">
                            <div>
                                <span className="detail__remaining-label">即獎剩餘數量</span>
                                <div className="detail__remaining-count">
                                    <strong>{detail.grandPrizeUnclaimed}</strong>
                                    <span> / {detail.grandPrizeCount} 個</span>
                                </div>
                            </div>
                            {detail.salesRateValue > 80 && (
                                <span className="detail__hot-badge">
                                    <TrendingUp size={14} />
                                    高銷快訊
                                </span>
                            )}
                        </div>
                        <div className="detail__remaining-bar">
                            <div
                                className="detail__remaining-fill"
                                style={{ width: `${detail.grandPrizeCount > 0 ? ((detail.grandPrizeCount - detail.grandPrizeUnclaimed) / detail.grandPrizeCount) * 100 : 0}%` }}
                            />
                        </div>
                        <div className="detail__remaining-info">
                            <span>已開出 {detail.grandPrizeCount - detail.grandPrizeUnclaimed} 個</span>
                            <span>尚有 {detail.grandPrizeUnclaimed} 個未開出</span>
                        </div>
                    </section>
                )}

                {/* 獨家特色 */}
                {features.length > 0 && (
                    <section className="detail__features">
                        <h2 className="detail__section-title">
                            <Sparkles size={20} />
                            獨家特色
                        </h2>
                        <div className="detail__features-grid">
                            {features.map((f, i) => (
                                <div key={i} className="detail__feature-card glass-card">
                                    <div className="detail__feature-icon">{f.icon}</div>
                                    <strong>{f.title}</strong>
                                    <p>{f.desc}</p>
                                </div>
                            ))}
                        </div>
                    </section>
                )}

                {/* 獎金結構表 */}
                <section className="detail__section glass-card">
                    <h2 className="detail__section-title">
                        <Trophy size={20} />
                        獎金結構
                    </h2>
                    {detail.prizes.length > 0 ? (
                        <div className="detail__table-wrap">
                            <table className="detail__table">
                                <thead>
                                    <tr>
                                        <th>獎項</th>
                                        <th>金額</th>
                                        <th>總數</th>
                                        <th>剩餘</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {detail.prizes.map((p, i) => {
                                        // 估算剩餘：依銷售率估算已開出比例
                                        const salesRatio = detail.salesRateValue / 100
                                        const estimatedRemaining = Math.round(p.totalCount * (1 - salesRatio))
                                        return (
                                            <tr key={i}>
                                                <td>{p.prizeName}</td>
                                                <td className="detail__amount">
                                                    {p.prizeAmount > 0 ? `$${p.prizeAmount.toLocaleString()}` : '-'}
                                                </td>
                                                <td>{p.totalCount.toLocaleString()}</td>
                                                <td className="detail__remaining-count-cell">
                                                    {estimatedRemaining.toLocaleString()}
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                            <p className="detail__table-note">
                                * 剩餘數量為依銷售率估算，僅供參考
                            </p>
                        </div>
                    ) : (
                        <p className="detail__empty">
                            {detail.isPreview
                                ? '預告款尚未公佈完整獎金結構，正式發售後將自動更新'
                                : '暫無獎金結構資料'}
                        </p>
                    )}
                </section>

                {/* 附近有貨店家 */}
                <section className="detail__section glass-card">
                    <h2 className="detail__section-title">
                        <Store size={20} />
                        附近有貨店家
                    </h2>
                    {!showNearby ? (
                        <div style={{ textAlign: 'center', padding: '1.5rem' }}>
                            <button
                                className="detail__nearby-btn"
                                onClick={loadNearbyStores}
                                disabled={nearbyLoading}
                            >
                                <MapPin size={18} />
                                查詢附近有貨的店家
                            </button>
                            <p style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.5rem' }}>
                                開啟 GPS 可依距離排序
                            </p>
                        </div>
                    ) : nearbyLoading ? (
                        <div style={{ textAlign: 'center', padding: '2rem' }}>
                            <div className="spinner" />
                            <p>搜尋附近有貨店家中...</p>
                        </div>
                    ) : nearbyStores.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
                            <Store size={36} style={{ opacity: 0.3, marginBottom: '0.5rem' }} />
                            <p>目前尚無店家回報此款式的庫存</p>
                        </div>
                    ) : (
                        <div className="detail__nearby-list">
                            {nearbyStores.map(store => (
                                <div key={store.retailerId} className="detail__nearby-store">
                                    <div className="detail__nearby-store-info">
                                        <strong className="detail__nearby-store-name">
                                            {store.retailerName}
                                            {store.merchantTier === 'pro' && <span className="detail__pro-badge">👑 PRO</span>}
                                        </strong>
                                        <span className="detail__nearby-store-address">
                                            📍 {store.address}
                                        </span>
                                        {store.distance !== null && (
                                            <span className="detail__nearby-store-distance">
                                                📏 {store.distance >= 1000 ? `${(store.distance / 1000).toFixed(1)} km` : `${store.distance} m`}
                                            </span>
                                        )}
                                    </div>
                                    <div className="detail__nearby-store-actions">
                                        <span className={`detail__nearby-status detail__nearby-status--${store.status === '充足' ? 'green' : 'yellow'}`}>
                                            {store.status === '充足' ? '🟢' : '🟡'} {store.status}
                                        </span>
                                        <a
                                            href={`https://www.google.com/maps/search/${encodeURIComponent(store.retailerName + ' ' + store.address)}`}
                                            target="_blank"
                                            rel="noreferrer"
                                            className="detail__nearby-nav"
                                        >
                                            <Navigation size={14} /> 導航
                                        </a>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </section>

                {/* 殘值計算機 — 每本獎項分佈 */}
                <section className="detail__section glass-card">
                    <h2 className="detail__section-title">
                        <Calculator size={20} />
                        殘值計算機
                    </h2>
                    <div className="calculator">
                        {/* 基本參數 */}
                        <div className="calculator__params">
                            <label className="calculator__label">
                                <span>總發行張數</span>
                                <strong>{detail.totalIssued.toLocaleString()}</strong>
                            </label>
                            <label className="calculator__label">
                                <span>每本張數</span>
                                <input
                                    type="number"
                                    className="calculator__input"
                                    min={1}
                                    value={ticketsPerBook}
                                    onChange={(e) => setTicketsPerBook(Math.max(1, Number(e.target.value)))}
                                />
                            </label>
                            {bookAnalysis && (
                                <label className="calculator__label">
                                    <span>發行本數</span>
                                    <strong>{Math.round(bookAnalysis.totalBooks).toLocaleString()}</strong>
                                </label>
                            )}
                            {bookAnalysis && (
                                <label className="calculator__label">
                                    <span>理論返還率</span>
                                    <strong className={bookAnalysis.returnRate >= 100 ? 'text-green' : 'text-red'}>
                                        {bookAnalysis.returnRate}%
                                    </strong>
                                </label>
                            )}
                        </div>

                        {/* 實務返還率拉桿 */}
                        {bookAnalysis && (() => {
                            const sliderMax = bookAnalysis.returnRate
                            const sliderMin = 55
                            const clampedMax = Math.max(sliderMin, sliderMax)
                            return (
                                <div className="calculator__slider-section">
                                    <div className="calculator__slider-header">
                                        <span className="calculator__slider-label">實務返還率調整</span>
                                        <strong className={practicalRate >= 100 ? 'text-green' : 'text-red'}>
                                            {practicalRate}%
                                        </strong>
                                    </div>
                                    <input
                                        type="range"
                                        className="calculator__slider"
                                        min={sliderMin}
                                        max={clampedMax}
                                        step={0.5}
                                        value={Math.min(practicalRate, clampedMax)}
                                        onChange={(e) => setPracticalRate(Number(e.target.value))}
                                    />
                                    <div className="calculator__slider-range">
                                        <span>{sliderMin}%</span>
                                        <span>理論最高 {sliderMax}%</span>
                                    </div>
                                    <p className="calculator__slider-hint">
                                        ℹ️ 實際中大獎機率極低，建議以 60% 作為實務參考值
                                    </p>
                                </div>
                            )
                        })()}

                        {/* 每本獎項分佈表 */}
                        {bookAnalysis && (
                            <div className="calculator__book-table-wrap">
                                <table className="calculator__book-table">
                                    <thead>
                                        <tr>
                                            <th>獎項</th>
                                            <th>金額</th>
                                            <th>每本張數</th>
                                            <th>已開出</th>
                                            <th>剩餘</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {bookAnalysis.rows.map((row, idx) => (
                                            <tr key={idx}>
                                                <td>{row.prizeName}</td>
                                                <td className="detail__amount">
                                                    {row.prizeAmount > 0 ? `$${row.prizeAmount.toLocaleString()}` : '-'}
                                                </td>
                                                <td className="calculator__per-book">
                                                    {row.perBook < 1
                                                        ? row.perBook.toFixed(4)
                                                        : row.perBook.toFixed(1)}
                                                </td>
                                                <td>
                                                    <input
                                                        type="number"
                                                        className="calculator__opened-input"
                                                        min={0}
                                                        value={openedCounts[idx] || 0}
                                                        onChange={(e) => updateOpened(idx, Number(e.target.value))}
                                                    />
                                                </td>
                                                <td className={row.remaining > 0 ? 'text-green' : 'text-muted'}>
                                                    {row.remaining < 1
                                                        ? row.remaining.toFixed(1)
                                                        : row.remaining.toFixed(1)}
                                                </td>
                                            </tr>
                                        ))}
                                        {/* 未中獎（0元） */}
                                        <tr className="calculator__zero-row">
                                            <td>未中獎</td>
                                            <td>$0</td>
                                            <td>{bookAnalysis.zeroTicketsPerBook.toFixed(1)}</td>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="calculator__opened-input"
                                                    min={0}
                                                    value={openedZero}
                                                    onChange={(e) => setOpenedZero(Math.max(0, Number(e.target.value)))}
                                                />
                                            </td>
                                            <td className={bookAnalysis.zeroTicketsPerBook - openedZero > 0 ? 'text-muted' : 'text-muted'}>
                                                {Math.max(0, bookAnalysis.zeroTicketsPerBook - openedZero).toFixed(1)}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        )}

                        {/* 殘值分析結果 */}
                        {bookAnalysis && bookAnalysis.totalOpened > 0 && (
                            <div className="calculator__results">
                                <div className="calculator__stat">
                                    <span>已開張數</span>
                                    <strong>{bookAnalysis.totalOpened}</strong>
                                </div>
                                <div className="calculator__stat">
                                    <span>剩餘張數</span>
                                    <strong>{bookAnalysis.remainingTickets}</strong>
                                </div>
                                <div className="calculator__stat">
                                    <span>剩餘預估獎金</span>
                                    <strong className={bookAnalysis.remainingValue > 0 ? 'text-green' : 'text-red'}>
                                        ${Math.round(bookAnalysis.remainingValue).toLocaleString()}
                                    </strong>
                                </div>
                                <div className="calculator__stat">
                                    <span>剩餘成本</span>
                                    <strong>
                                        ${bookAnalysis.costRemaining.toLocaleString()}
                                    </strong>
                                </div>
                                <div className="calculator__stat">
                                    <span>殘值投報率</span>
                                    <strong className={bookAnalysis.remainingValue >= bookAnalysis.costRemaining ? 'text-green' : 'text-red'}>
                                        {bookAnalysis.costRemaining > 0
                                            ? `${Math.round((bookAnalysis.remainingValue / bookAnalysis.costRemaining) * 100)}%`
                                            : '-'}
                                    </strong>
                                </div>
                            </div>
                        )}
                    </div>
                </section>

                {/* 實況開箱影片 — 嵌入 YouTube 播放清單 */}
                <section className="detail__section">
                    <h2 className="detail__section-title">
                        <Play size={20} />
                        實況開箱影片
                    </h2>
                    <div className="detail__video-embed">
                        <iframe
                            className="detail__video-iframe"
                            src={`https://www.youtube.com/embed/videoseries?list=${REVIEW_PLAYLIST_ID}`}
                            title={`${detail.name} 開箱影片`}
                            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                            allowFullScreen
                        />
                    </div>
                </section>

                {/* 時間資訊 */}
                <div className="detail__dates glass-card">
                    <div className="detail__date-item">
                        <Calendar size={14} />
                        <span>上市日</span>
                        <strong>{detail.issueDate || '-'}</strong>
                    </div>
                    <div className="detail__date-item">
                        <Calendar size={14} />
                        <span>下市日</span>
                        <strong>{detail.endDate || '-'}</strong>
                    </div>
                    <div className="detail__date-item">
                        <Calendar size={14} />
                        <span>兌獎截止</span>
                        <strong>{detail.redeemDeadline || '-'}</strong>
                    </div>
                    <div className="detail__date-item">
                        <DollarSign size={14} />
                        <span>銷售率</span>
                        <strong>{detail.salesRate || '-'}</strong>
                    </div>
                </div>
            </motion.div>
        </div>
    )
}
