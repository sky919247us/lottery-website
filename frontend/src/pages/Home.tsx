/**
 * 首頁 — 刮刮樂列表
 * 排序 Tab、過期篩選、本週推薦、熱門判定、卡片標籤與熱銷度進度條
 */
import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Search, AlertTriangle, TrendingUp, Trophy, Flame, Sparkles, Percent, SlidersHorizontal, X, CalendarClock } from 'lucide-react'
import { fetchScratchcards, fetchPreviewScratchcards, type ScratchcardListItem } from '../hooks/api'
import SeoHead from '../components/SeoHead'
import './Home.css'

/** 排序選項 */
type SortMode = 'hot' | 'price' | 'newest' | 'winRate'

const SORT_TABS: { key: SortMode; label: string; icon: React.ReactNode }[] = [
    { key: 'hot', label: '熱門排行', icon: <Flame size={14} /> },
    { key: 'price', label: '價格高低', icon: null },
    { key: 'newest', label: '最新上市', icon: null },
    { key: 'winRate', label: '中獎率', icon: null },
]

/**
 * 解析民國年日期字串為 Date 物件
 * 支援格式如 "113/01/15" 或 "113.01.15"
 */
function parseRocDate(dateStr: string): Date | null {
    if (!dateStr) return null
    const cleaned = dateStr.replace(/\./g, '/')
    const parts = cleaned.split('/')
    if (parts.length !== 3) return null
    const year = parseInt(parts[0]) + 1911
    const month = parseInt(parts[1]) - 1
    const day = parseInt(parts[2])
    if (isNaN(year) || isNaN(month) || isNaN(day)) return null
    return new Date(year, month, day)
}

/**
 * 解析 overallWinRate 字串為數值
 * 例如 "69.33%" → 69.33
 */
function parseWinRate(winRate: string): number {
    if (!winRate) return 0
    const num = parseFloat(winRate.replace('%', ''))
    return isNaN(num) ? 0 : num
}

/**
 * 判斷是否為過期彩券
 * 條件1：兌獎截止日已過
 * 條件2：銷售率 100%（已完售）
 */
function isExpired(card: ScratchcardListItem): boolean {
    // 銷售率達 100% 即視為過期
    if (card.salesRateValue >= 100) return true
    // 兌獎截止日已過
    const deadline = parseRocDate(card.redeemDeadline)
    if (!deadline) return false
    return deadline < new Date()
}

/**
 * 判斷是否為熱門款
 * 條件1：中獎率超過 49%
 * 條件2：往年同名遊戲銷售率高（salesRateValue > 70）→ 今年同名自動標記
 */
function isHotCard(card: ScratchcardListItem, allCards: ScratchcardListItem[]): boolean {
    // 條件1：中獎率超過 49%
    if (parseWinRate(card.overallWinRate) > 49) return true

    // 條件2：同名遊戲中，有往年款式銷售率高的
    const sameName = allCards.filter(c => c.name === card.name && c.id !== card.id)
    const hasHighSalesHistory = sameName.some(c => c.salesRateValue > 70)
    if (hasHighSalesHistory) return true

    // 自身銷售率高也算熱門
    if (card.salesRateValue > 70) return true

    return false
}

/**
 * 判斷是否為新上架（30天內）
 */
function isNewCard(card: ScratchcardListItem): boolean {
    const issueDate = parseRocDate(card.issueDate)
    if (!issueDate) return false
    const diffDays = Math.floor((Date.now() - issueDate.getTime()) / (1000 * 60 * 60 * 24))
    return diffDays <= 30
}

/**
 * 判斷是否已完售
 */
function isSoldOut(card: ScratchcardListItem): boolean {
    return card.salesRateValue >= 99
}

export default function Home() {
    const [cards, setCards] = useState<ScratchcardListItem[]>([])
    const [previewCards, setPreviewCards] = useState<ScratchcardListItem[]>([])
    const [loading, setLoading] = useState(true)
    const [search, setSearch] = useState('')
    const [sortMode, setSortMode] = useState<SortMode>('newest')
    const [showExpired, setShowExpired] = useState(false)
    const [showFilters, setShowFilters] = useState(false)

    // 進階篩選
    const [priceFilter, setPriceFilter] = useState<number[]>([])
    const [maxPrizeMin, setMaxPrizeMin] = useState('')
    const [maxPrizeMax, setMaxPrizeMax] = useState('')

    /** 可選面額 */
    const PRICE_OPTIONS = [100, 200, 300, 500, 1000, 2000]

    useEffect(() => {
        loadData()
    }, [])

    async function loadData() {
        const CACHE_KEY = 'scratchcards_cache'
        const CACHE_TTL = 24 * 60 * 60 * 1000 // 24 小時（台彩每天 09:00 更新一次）

        // 先讀 localStorage 快取 → 立即顯示（不等 API）
        try {
            const raw = localStorage.getItem(CACHE_KEY)
            if (raw) {
                const { data, ts } = JSON.parse(raw)
                if (Date.now() - ts < CACHE_TTL && Array.isArray(data) && data.length > 0) {
                    setCards(data)
                    setLoading(false)
                    // 後台靜默刷新（stale-while-revalidate）
                    Promise.all([
                        fetchScratchcards({ sortBy: 'issueDate', order: 'desc', isPreview: false }),
                        fetchPreviewScratchcards(),
                    ]).then(([fresh, freshPreviews]) => {
                        setCards(fresh)
                        setPreviewCards(freshPreviews)
                        localStorage.setItem(CACHE_KEY, JSON.stringify({ data: fresh, ts: Date.now() }))
                    }).catch(() => {})
                    return
                }
            }
        } catch { /* localStorage 不可用，繼續正常流程 */ }

        // 無快取 → 正常 fetch
        try {
            setLoading(true)
            const [data, previews] = await Promise.all([
                fetchScratchcards({ sortBy: 'issueDate', order: 'desc', isPreview: false }),
                fetchPreviewScratchcards(),
            ])
            setCards(data)
            setPreviewCards(previews)
            localStorage.setItem(CACHE_KEY, JSON.stringify({ data, ts: Date.now() }))
        } catch {
            setCards([])
            setPreviewCards([])
        } finally {
            setLoading(false)
        }
    }

    /** 篩選 + 排序後的列表 */
    const processedCards = useMemo(() => {
        let result = [...cards]

        // 搜尋篩選
        if (search) {
            result = result.filter(c =>
                c.name.includes(search) || c.gameId.includes(search)
            )
        }

        // 面額篩選
        if (priceFilter.length > 0) {
            result = result.filter(c => priceFilter.includes(c.price))
        }

        // 最高獎金區間篩選
        const minPrize = maxPrizeMin ? parseInt(maxPrizeMin) * 10000 : 0
        const maxPrize = maxPrizeMax ? parseInt(maxPrizeMax) * 10000 : Infinity
        if (minPrize > 0 || maxPrize < Infinity) {
            result = result.filter(c => c.maxPrizeAmount >= minPrize && c.maxPrizeAmount <= maxPrize)
        }

        // 過期篩選
        if (!showExpired) {
            result = result.filter(c => !isExpired(c))
        }

        // 排序
        switch (sortMode) {
            case 'hot':
                // 熱門排行：熱門款優先，再依銷售率降序
                result.sort((a, b) => {
                    const aHot = isHotCard(a, cards) ? 1 : 0
                    const bHot = isHotCard(b, cards) ? 1 : 0
                    if (bHot !== aHot) return bHot - aHot
                    return b.salesRateValue - a.salesRateValue
                })
                break
            case 'price':
                result.sort((a, b) => b.price - a.price)
                break
            case 'newest':
                result.sort((a, b) => {
                    const dateA = parseRocDate(a.issueDate)
                    const dateB = parseRocDate(b.issueDate)
                    return (dateB?.getTime() || 0) - (dateA?.getTime() || 0)
                })
                break
            case 'winRate':
                result.sort((a, b) => parseWinRate(b.overallWinRate) - parseWinRate(a.overallWinRate))
                break
        }

        return result
    }, [cards, search, sortMode, showExpired, priceFilter, maxPrizeMin, maxPrizeMax])

    /** 是否有任何篩選條件 */
    const hasActiveFilters = priceFilter.length > 0 || maxPrizeMin !== '' || maxPrizeMax !== ''

    /** 清除全部篩選 */
    const clearFilters = () => {
        setPriceFilter([])
        setMaxPrizeMin('')
        setMaxPrizeMax('')
    }

    /** 切換面額篩選（多選） */
    const togglePrice = (price: number) => {
        setPriceFilter(prev =>
            prev.includes(price) ? prev.filter(p => p !== price) : [...prev, price]
        )
    }

    /**
     * 本週推薦：5 個推薦位，各自有不同的推薦邏輯
     */
    const recommendedCards = useMemo(() => {
        const valid = cards.filter(c => !isExpired(c))
        if (valid.length === 0) return []

        type RecommendSlot = {
            emoji: string
            title: string
            subtitle: string
            card: ScratchcardListItem | null
        }

        const slots: RecommendSlot[] = []

        // 🥇 本週最佳 CP — ROI（中獎率×回本期望）最高
        const bestCp = [...valid]
            .filter(c => parseWinRate(c.overallWinRate) > 0)
            .sort((a, b) => parseWinRate(b.overallWinRate) - parseWinRate(a.overallWinRate))[0]
        if (bestCp) {
            slots.push({ emoji: '🥇', title: '本週最佳 CP', subtitle: '中獎機率最高', card: bestCp })
        }

        // 🔥 熱銷款 — 銷售率最高且未售完
        const hotSelling = [...valid]
            .filter(c => c.salesRateValue > 0 && c.salesRateValue < 100)
            .sort((a, b) => b.salesRateValue - a.salesRateValue)[0]
        if (hotSelling && hotSelling.id !== bestCp?.id) {
            slots.push({ emoji: '🔥', title: '熱銷款', subtitle: '大家都在買', card: hotSelling })
        }

        // 🆕 新上架 — 30天內 + 中獎率 > 25%
        const freshNew = [...valid]
            .filter(c => isNewCard(c) && parseWinRate(c.overallWinRate) > 25)
            .sort((a, b) => parseWinRate(b.overallWinRate) - parseWinRate(a.overallWinRate))[0]
        if (freshNew && !slots.some(s => s.card?.id === freshNew.id)) {
            slots.push({ emoji: '🆕', title: '新上架', subtitle: '剛上市，搶先體驗', card: freshNew })
        }

        // 💰 頭獎獵人 — 頭獎金額最高 + 頭獎還有剩
        const jackpotHunter = [...valid]
            .filter(c => c.grandPrizeUnclaimed > 0)
            .sort((a, b) => b.maxPrizeAmount - a.maxPrizeAmount)[0]
        if (jackpotHunter && !slots.some(s => s.card?.id === jackpotHunter.id)) {
            slots.push({ emoji: '💰', title: '頭獎獵人', subtitle: '頭獎仍在，值得一搏', card: jackpotHunter })
        }

        // 🎯 小資首選 — 售價 ≤ $200 + 中獎率最高
        const budgetPick = [...valid]
            .filter(c => c.price <= 200 && parseWinRate(c.overallWinRate) > 0)
            .sort((a, b) => parseWinRate(b.overallWinRate) - parseWinRate(a.overallWinRate))[0]
        if (budgetPick && !slots.some(s => s.card?.id === budgetPick.id)) {
            slots.push({ emoji: '🎯', title: '小資首選', subtitle: '小額投入，高機率中獎', card: budgetPick })
        }

        return slots.filter(s => s.card !== null)
    }, [cards])

    /** 輪播 index */
    const [featuredIndex, setFeaturedIndex] = useState(0)

    // NOTE: 自動輪播每 5 秒切換
    useEffect(() => {
        if (recommendedCards.length <= 1) return
        const timer = setInterval(() => {
            setFeaturedIndex(prev => (prev + 1) % recommendedCards.length)
        }, 5000)
        return () => clearInterval(timer)
    }, [recommendedCards.length])

    /** 計算 Top 10% 門檻 */
    const top10Threshold = useMemo(() => {
        const sorted = [...cards].sort((a, b) => b.salesRateValue - a.salesRateValue)
        const idx = Math.max(0, Math.floor(sorted.length * 0.1) - 1)
        return sorted[idx]?.salesRateValue || 100
    }, [cards])

    return (
        <div className="home">
            <SeoHead
                title="刮刮研究室 — 中獎率分析 × 殘值計算"
                description="全台最完整的刮刮樂情報平台。即時查看各款刮刮樂的中獎率、銷售率、頭獎剩餘與殘值分析，幫助你做出最聰明的購買決策。"
                path="/"
            />
            {/* Hero 區塊 */}
            <section className="home__hero">
                <motion.h1
                    className="home__title"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    🎰 刮刮研究室
                </motion.h1>
                <motion.p
                    className="home__subtitle"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, delay: 0.1 }}
                >
                    即時查看各款刮刮樂的獎金結構、銷售率與殘值分析
                </motion.p>
            </section>

            {/* 搜尋列 */}
            <section className="home__filters container">
                <div className="home__search">
                    <Search size={18} />
                    <input
                        type="text"
                        placeholder="搜尋遊戲名稱或編號..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>

                {/* 排序 Tab */}
                <div className="home__sort-tabs">
                    {SORT_TABS.map((tab) => (
                        <button
                            key={tab.key}
                            className={`sort-tab ${sortMode === tab.key ? 'sort-tab--active' : ''}`}
                            onClick={() => setSortMode(tab.key)}
                        >
                            {tab.icon}
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* 過期彩券核選按鈕 */}
                <label className="home__expired-toggle">
                    <input
                        type="checkbox"
                        checked={showExpired}
                        onChange={(e) => setShowExpired(e.target.checked)}
                    />
                    <span className="home__expired-checkbox" />
                    <span>顯示過期彩券</span>
                </label>

                {/* 進階篩選切換按鈕 */}
                <button
                    className={`home__filter-toggle ${showFilters || hasActiveFilters ? 'home__filter-toggle--active' : ''}`}
                    onClick={() => setShowFilters(!showFilters)}
                >
                    <SlidersHorizontal size={14} />
                    進階篩選
                    {hasActiveFilters && <span className="home__filter-badge">!</span>}
                </button>

                {/* 進階篩選面板 */}
                {showFilters && (
                    <div className="home__advanced-filters">
                        {/* 面額篩選 */}
                        <div className="home__filter-group">
                            <span className="home__filter-label">面額篩選</span>
                            <div className="home__filter-chips">
                                {PRICE_OPTIONS.map(price => (
                                    <button
                                        key={price}
                                        className={`filter-chip ${priceFilter.includes(price) ? 'filter-chip--active' : ''}`}
                                        onClick={() => togglePrice(price)}
                                    >
                                        ${price}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* 最高獎金區間 */}
                        <div className="home__filter-group">
                            <span className="home__filter-label">最高獎金（萬元）</span>
                            <div className="home__filter-range">
                                <input
                                    type="number"
                                    placeholder="最低"
                                    value={maxPrizeMin}
                                    onChange={e => setMaxPrizeMin(e.target.value)}
                                    min="0"
                                />
                                <span className="home__filter-range-sep">～</span>
                                <input
                                    type="number"
                                    placeholder="最高"
                                    value={maxPrizeMax}
                                    onChange={e => setMaxPrizeMax(e.target.value)}
                                    min="0"
                                />
                            </div>
                        </div>

                        {/* 清除篩選 */}
                        {hasActiveFilters && (
                            <button className="home__clear-filters" onClick={clearFilters}>
                                <X size={14} />
                                清除全部篩選
                            </button>
                        )}
                    </div>
                )}
            </section>

            {/* 即將發售專區 */}
            {previewCards.length > 0 && !loading && (
                <section className="home__preview container">
                    <h2 className="home__section-title">
                        <CalendarClock size={18} />
                        即將發售
                    </h2>
                    <div className="home__preview-grid">
                        {previewCards.map((card, index) => (
                            <motion.div
                                key={card.id}
                                initial={{ opacity: 0, y: 20 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ duration: 0.4, delay: index * 0.05 }}
                            >
                                <article className="scratch-card glass-card scratch-card--preview">
                                    <div className="scratch-card__tags">
                                        <span className="scratch-card__tag scratch-card__tag--preview">即將發售</span>
                                    </div>
                                    <div className="scratch-card__image">
                                        {card.imageUrl ? (
                                            <img src={card.imageUrl} alt={card.name} loading="lazy" />
                                        ) : (
                                            <div className="scratch-card__placeholder">🎫</div>
                                        )}
                                    </div>
                                    <div className="scratch-card__info">
                                        <h3 className="scratch-card__name">{card.name}</h3>
                                        <span className="scratch-card__price">${card.price}</span>
                                        {card.maxPrizeAmount > 0 && (
                                            <div className="scratch-card__max-prize">
                                                <span className="scratch-card__max-prize-label">頭獎</span>
                                                <strong className="scratch-card__max-prize-value">
                                                    {card.maxPrizeAmount >= 10000
                                                        ? `${card.maxPrizeAmount / 10000}萬元`
                                                        : `${card.maxPrizeAmount.toLocaleString()}元`}
                                                </strong>
                                            </div>
                                        )}
                                        <div className="scratch-card__stats">
                                            {card.issueDate && (
                                                <div className="stat">
                                                    <CalendarClock size={14} />
                                                    <span>預計上市 {card.issueDate}</span>
                                                </div>
                                            )}
                                            {card.overallWinRate && card.overallWinRate !== '—' && (
                                                <div className="stat">
                                                    <Percent size={14} />
                                                    <span>中獎率 {card.overallWinRate}</span>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                </article>
                            </motion.div>
                        ))}
                    </div>
                </section>
            )}

            {/* 本週推薦 — 輪播多張 */}
            {recommendedCards.length > 0 && !loading && (
                <section className="home__featured container">
                    <h2 className="home__section-title">
                        <Sparkles size={18} />
                        本週推薦
                    </h2>

                    {/* 推薦 Tab 切換 */}
                    <div className="featured-tabs">
                        {recommendedCards.map((slot, i) => (
                            <button
                                key={i}
                                className={`featured-tab ${i === featuredIndex ? 'featured-tab--active' : ''}`}
                                onClick={() => setFeaturedIndex(i)}
                            >
                                <span className="featured-tab__emoji">{slot.emoji}</span>
                                <span className="featured-tab__title">{slot.title}</span>
                            </button>
                        ))}
                    </div>

                    {/* 推薦卡片 */}
                    {recommendedCards[featuredIndex] && (() => {
                        const slot = recommendedCards[featuredIndex]
                        const card = slot.card!
                        return (
                            <Link to={`/detail/${card.id}`} className="card-link">
                                <motion.div
                                    className="featured-card"
                                    key={`featured-${card.id}`}
                                    initial={false}
                                    animate={{ opacity: 1 }}
                                    transition={{ duration: 0.3 }}
                                >
                                    <div className="featured-card__image">
                                        {card.imageUrl ? (
                                            <img src={card.imageUrl} alt={card.name} loading="lazy" />
                                        ) : (
                                            <div className="featured-card__placeholder">🎫</div>
                                        )}
                                    </div>
                                    <div className="featured-card__info">
                                        <div className="featured-card__recommend-tag">
                                            <span>{slot.emoji}</span>
                                            <span>{slot.subtitle}</span>
                                        </div>
                                        {card.maxPrizeAmount > 0 && (
                                            <div className="featured-card__prize-badge">
                                                最高獎金 {card.maxPrizeAmount >= 10000
                                                    ? `${card.maxPrizeAmount / 10000}萬元`
                                                    : `${card.maxPrizeAmount.toLocaleString()}元`}
                                            </div>
                                        )}
                                        <h3 className="featured-card__name">{card.name}</h3>
                                        <div className="featured-card__meta">
                                            <span>每張售價 ${card.price.toLocaleString()}</span>
                                            {card.overallWinRate && (
                                                <span className="featured-card__winrate">
                                                    <TrendingUp size={14} />
                                                    中獎率 {card.overallWinRate}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                </motion.div>
                            </Link>
                        )
                    })()}

                    {/* 輪播指示器 */}
                    {recommendedCards.length > 1 && (
                        <div className="featured-dots">
                            {recommendedCards.map((_, i) => (
                                <button
                                    key={i}
                                    className={`featured-dot ${i === featuredIndex ? 'featured-dot--active' : ''}`}
                                    onClick={() => setFeaturedIndex(i)}
                                />
                            ))}
                        </div>
                    )}
                </section>
            )}

            {/* 全部遊戲 */}
            <section className="home__list-section container">
                <div className="home__list-header">
                    <h2 className="home__section-title">全部遊戲</h2>
                    <span className="home__count">共 {processedCards.length} 款</span>
                </div>

                <div className="home__grid">
                    {loading ? (
                        Array.from({ length: 12 }).map((_, i) => (
                            <div key={i} className="skeleton-card">
                                <div className="skeleton-block skeleton-image" />
                                <div className="skeleton-block skeleton-title" />
                                <div className="skeleton-block skeleton-sub" />
                                <div className="skeleton-block skeleton-bar" />
                            </div>
                        ))
                    ) : processedCards.length === 0 ? (
                        <div className="home__empty">
                            <Trophy size={48} />
                            <p>
                                {cards.length === 0
                                    ? '尚無資料，請先執行後端爬蟲'
                                    : '找不到符合條件的刮刮樂'}
                            </p>
                        </div>
                    ) : (
                        processedCards.map((card, index) => {
                            const hot = isHotCard(card, cards)
                            const isNew = isNewCard(card)
                            const soldOut = isSoldOut(card)
                            const isTop10 = card.salesRateValue >= top10Threshold && card.salesRateValue > 0
                            const expired = isExpired(card)

                            return (
                                <motion.div
                                    key={card.id}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: index * 0.03 }}
                                >
                                    <Link to={`/detail/${card.id}`} className="card-link">
                                        <article className={`scratch-card glass-card ${card.isHighWinRate ? 'scratch-card--alert' : ''} ${expired ? 'scratch-card--expired' : ''}`}>
                                            {/* 標籤群組 */}
                                            <div className="scratch-card__tags">
                                                {isTop10 && !soldOut && (
                                                    <span className="scratch-card__tag scratch-card__tag--top">Top 10%</span>
                                                )}
                                                {hot && !soldOut && (
                                                    <span className="scratch-card__tag scratch-card__tag--hot">🔥 熱門</span>
                                                )}
                                                {isNew && (
                                                    <span className="scratch-card__tag scratch-card__tag--new">NEW</span>
                                                )}
                                                {soldOut && (
                                                    <span className="scratch-card__tag scratch-card__tag--sold">已完售</span>
                                                )}
                                                {expired && !soldOut && (
                                                    <span className="scratch-card__tag scratch-card__tag--expired">已過期</span>
                                                )}
                                            </div>

                                            {/* 紅色警戒徽章 — 依高勝率或頭獎殘值判定 */}
                                            {(card.isHighWinRate || (card.grandPrizeUnclaimed > 0 && card.salesRateValue > 85)) && (
                                                <div className="scratch-card__badge">
                                                    <AlertTriangle size={14} />
                                                    <span>{card.isHighWinRate ? '高勝率預警' : '頭獎仍在'}</span>
                                                </div>
                                            )}

                                            {/* 圖片 */}
                                            <div className="scratch-card__image">
                                                {card.imageUrl ? (
                                                    <img src={card.imageUrl} alt={card.name} loading="lazy" />
                                                ) : (
                                                    <div className="scratch-card__placeholder">🎫</div>
                                                )}
                                            </div>

                                            {/* 資訊 */}
                                            <div className="scratch-card__info">
                                                <h3 className="scratch-card__name">{card.name}</h3>
                                                <span className="scratch-card__price">${card.price}</span>
                                                <div className="scratch-card__stats">
                                                    {card.salesRate && (
                                                        <div className="stat">
                                                            <TrendingUp size={14} />
                                                            <span>銷售率 {card.salesRate}</span>
                                                        </div>
                                                    )}
                                                    <div className="stat">
                                                        <Percent size={14} />
                                                        <span>中獎率 {card.overallWinRate || '-'}</span>
                                                    </div>
                                                </div>

                                                {/* 最高獎金 — 底部高亮區 */}
                                                {card.maxPrizeAmount > 0 && (
                                                    <div className="scratch-card__max-prize">
                                                        <span className="scratch-card__max-prize-label">最高獎金</span>
                                                        <strong className="scratch-card__max-prize-value">
                                                            {card.maxPrizeAmount >= 10000
                                                                ? `${card.maxPrizeAmount / 10000}萬元`
                                                                : `${card.maxPrizeAmount.toLocaleString()}元`}
                                                        </strong>
                                                    </div>
                                                )}
                                            </div>
                                        </article>
                                    </Link>
                                </motion.div>
                            )
                        })
                    )}
                </div>
            </section>
        </div>
    )
}
