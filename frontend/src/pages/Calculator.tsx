/**
 * 殘值計算機頁面
 * 與首頁相同的刮刮樂列表（搜尋、排序），但不含本週推薦、不顯示過期彩券
 * 點擊任一款即可進入該款詳情頁使用殘值計算機
 */
import { useEffect, useState, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
    Search, AlertTriangle, TrendingUp, Trophy, Flame,
    Percent, Calculator, CalendarClock
} from 'lucide-react'
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

/** 解析民國年日期字串為 Date */
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

/** 解析中獎率字串為數值 */
function parseWinRate(winRate: string): number {
    if (!winRate) return 0
    const num = parseFloat(winRate.replace('%', ''))
    return isNaN(num) ? 0 : num
}

/** 判斷是否過期（銷售率 100% 或兌獎截止日已過） */
function isExpired(card: ScratchcardListItem): boolean {
    if (card.salesRateValue >= 100) return true
    const deadline = parseRocDate(card.redeemDeadline)
    if (!deadline) return false
    return deadline < new Date()
}

/** 判斷是否為熱門款 */
function isHotCard(card: ScratchcardListItem, allCards: ScratchcardListItem[]): boolean {
    if (parseWinRate(card.overallWinRate) > 49) return true
    const sameName = allCards.filter(c => c.name === card.name && c.id !== card.id)
    if (sameName.some(c => c.salesRateValue > 70)) return true
    if (card.salesRateValue > 70) return true
    return false
}

/** 判斷是否為新上架（30天內） */
function isNewCard(card: ScratchcardListItem): boolean {
    const issueDate = parseRocDate(card.issueDate)
    if (!issueDate) return false
    const diffDays = Math.floor((Date.now() - issueDate.getTime()) / (1000 * 60 * 60 * 24))
    return diffDays <= 30
}

/** 判斷是否已完售 */
function isSoldOut(card: ScratchcardListItem): boolean {
    return card.salesRateValue >= 99
}

export default function CalculatorPage() {
    const [cards, setCards] = useState<ScratchcardListItem[]>([])
    const [loading, setLoading] = useState(true)
    const [search, setSearch] = useState('')
    const [sortMode, setSortMode] = useState<SortMode>('newest')

    useEffect(() => {
        loadData()
    }, [])

    async function loadData() {
        try {
            setLoading(true)
            const [data, previews] = await Promise.all([
                fetchScratchcards({ sortBy: 'issueDate', order: 'desc', isPreview: false }),
                fetchPreviewScratchcards(),
            ])
            // 預告款排在最前面
            setCards([...previews, ...data])
        } catch {
            setCards([])
        } finally {
            setLoading(false)
        }
    }

    /** 篩選 + 排序（永遠排除過期彩券） */
    const processedCards = useMemo(() => {
        // 永遠排除過期彩券
        let result = cards.filter(c => !isExpired(c))

        // 搜尋篩選
        if (search) {
            result = result.filter(c =>
                c.name.includes(search) || c.gameId.includes(search)
            )
        }

        // 排序
        switch (sortMode) {
            case 'hot':
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
    }, [cards, search, sortMode])

    /** Top 10% 銷售率門檻 */
    const top10Threshold = useMemo(() => {
        const sorted = [...cards].sort((a, b) => b.salesRateValue - a.salesRateValue)
        const idx = Math.max(0, Math.floor(sorted.length * 0.1) - 1)
        return sorted[idx]?.salesRateValue || 100
    }, [cards])

    return (
        <div className="home">
            <SeoHead
                title="殘值計算機 — 刮刮樂每本獎金分佈分析"
                description="刮刮樂殘值計算機，計算每本刮刮樂的獎金分佈與剩餘殘值，幫助你判斷是否值得繼續刮。"
                path="/calculator"
            />
            {/* Hero 區塊 */}
            <section className="home__hero">
                <motion.h1
                    className="home__title"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    <Calculator size={32} />
                    殘值計算機
                </motion.h1>
                <motion.p
                    className="home__subtitle"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, delay: 0.1 }}
                >
                    選擇一款刮刮樂，進入詳情頁使用殘值計算機分析每本獎項分佈
                </motion.p>
            </section>

            {/* 搜尋列 + 排序 */}
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
            </section>

            {/* 刮刮樂列表（不含過期） */}
            <section className="home__list-section container">
                <div className="home__list-header">
                    <h2 className="home__section-title">選擇款式</h2>
                    <span className="home__count">共 {processedCards.length} 款</span>
                </div>

                <div className="home__grid">
                    {loading ? (
                        <div className="home__loading">
                            <div className="spinner" />
                            <p>載入中...</p>
                        </div>
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

                            return (
                                <motion.div
                                    key={card.id}
                                    initial={{ opacity: 0, y: 20 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: index * 0.03 }}
                                >
                                    {card.isPreview ? (
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
                                    ) : (
                                    <Link to={`/detail/${card.id}`} className="card-link">
                                        <article className={`scratch-card glass-card ${card.isHighWinRate ? 'scratch-card--alert' : ''}`}>
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
                                            </div>

                                            {/* 紅色警戒徽章 */}
                                            {card.isHighWinRate && (
                                                <div className="scratch-card__badge">
                                                    <AlertTriangle size={14} />
                                                    <span>高勝率預警</span>
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
                                                    {card.salesRate ? (
                                                        <div className="stat">
                                                            <TrendingUp size={14} />
                                                            <span>銷售率 {card.salesRate}</span>
                                                        </div>
                                                    ) : null}
                                                    <div className="stat">
                                                        <Percent size={14} />
                                                        <span>中獎率 {card.overallWinRate || '-'}</span>
                                                    </div>
                                                </div>

                                                {/* 最高獎金 */}
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
                                    )}
                                </motion.div>
                            )
                        })
                    )}
                </div>
            </section>
        </div>
    )
}
