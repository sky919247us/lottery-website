/**
 * 店家評分顯示元件
 * 顯示平均星等、評分人數、標籤統計與最新評論
 */
import { useEffect, useState } from 'react'
import { Star, CheckCircle, MessageCircle } from 'lucide-react'
import { fetchRatingSummary, fetchRetailerRatings, type RatingSummaryData, type RatingData } from '../hooks/api'
import './RatingDisplay.css'

interface RatingDisplayProps {
    retailerId: number
    /** 僅顯示簡潔的星等 + 人數（卡片模式） */
    compact?: boolean
}

export default function RatingDisplay({ retailerId, compact = false }: RatingDisplayProps) {
    const [summary, setSummary] = useState<RatingSummaryData | null>(null)
    const [reviews, setReviews] = useState<RatingData[]>([])
    const [showReviews, setShowReviews] = useState(false)

    useEffect(() => {
        fetchRatingSummary(retailerId)
            .then(setSummary)
            .catch(() => { })
    }, [retailerId])

    /** 載入評論列表 */
    function loadReviews() {
        if (reviews.length > 0) {
            setShowReviews(!showReviews)
            return
        }
        fetchRetailerRatings(retailerId)
            .then(data => {
                setReviews(data)
                setShowReviews(true)
            })
            .catch(() => { })
    }

    if (!summary || summary.totalCount === 0) {
        if (compact) return null
        return (
            <div className="rating-display rating-display--empty">
                <span className="rating-display__no-data">尚無評分</span>
            </div>
        )
    }

    /** 渲染星等 */
    function renderStars(value: number) {
        return (
            <div className="rating-display__stars">
                {[1, 2, 3, 4, 5].map(n => (
                    <Star
                        key={n}
                        size={compact ? 14 : 16}
                        fill={n <= Math.round(value) ? '#d4af37' : 'none'}
                        color={n <= Math.round(value) ? '#d4af37' : 'var(--border-subtle)'}
                    />
                ))}
            </div>
        )
    }

    // 精簡模式：僅星等 + 人數
    if (compact) {
        return (
            <div className="rating-display rating-display--compact">
                {renderStars(summary.avgRating)}
                <span className="rating-display__avg">{summary.avgRating}</span>
                <span className="rating-display__count">({summary.totalCount})</span>
            </div>
        )
    }

    // 完整模式
    const topServiceTags = Object.entries(summary.serviceTagStats)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 4)

    return (
        <div className="rating-display">
            <div className="rating-display__header">
                {renderStars(summary.avgRating)}
                <span className="rating-display__avg">{summary.avgRating}</span>
                <span className="rating-display__count">({summary.totalCount} 則評分)</span>
            </div>

            {/* 標籤統計 */}
            {topServiceTags.length > 0 && (
                <div className="rating-display__tags">
                    {topServiceTags.map(([tag, count]) => (
                        <span key={tag} className="rating-display__tag-stat">
                            {tag}
                            <span className="rating-display__tag-pct">
                                {Math.round((count / summary.totalCount) * 100)}%
                            </span>
                        </span>
                    ))}
                </div>
            )}

            {/* 展開評論 */}
            <button className="rating-display__toggle-reviews" onClick={loadReviews}>
                <MessageCircle size={14} />
                {showReviews ? '收合評論' : `查看評論 (${summary.totalCount})`}
            </button>

            {showReviews && reviews.length > 0 && (
                <div className="rating-display__reviews">
                    {reviews.slice(0, 5).map(r => (
                        <div key={r.id} className="rating-display__review">
                            <div className="rating-display__review-header">
                                {r.userPictureUrl && (
                                    <img className="rating-display__review-avatar" src={r.userPictureUrl} alt="" />
                                )}
                                <span className="rating-display__review-name">
                                    {r.userName}
                                    <span className="rating-display__review-level">Lv.{r.userLevel}</span>
                                </span>
                                {r.isGpsVerified && (
                                    <CheckCircle size={14} className="rating-display__verified" />
                                )}
                                <div className="rating-display__review-stars">
                                    {[1, 2, 3, 4, 5].map(n => (
                                        <Star key={n} size={12} fill={n <= r.rating ? '#d4af37' : 'none'} color={n <= r.rating ? '#d4af37' : '#555'} />
                                    ))}
                                </div>
                            </div>
                            {r.comment && <p className="rating-display__review-text">{r.comment}</p>}
                            {r.serviceTags.length > 0 && (
                                <div className="rating-display__review-tags">
                                    {r.serviceTags.map(t => <span key={t} className="rating-display__mini-tag">{t}</span>)}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
