/**
 * 投注站服務品質評分面板（Modal）
 * 含星等、服務標籤、硬體設施群眾回報、文字評論
 */
import { useState } from 'react'
import { Star, MapPin, X } from 'lucide-react'
import { submitRating } from '../hooks/api'
import { useAuth } from '../hooks/useAuth'
import './RatingPanel.css'

/** 服務品質標籤 */
const SERVICE_TAGS = [
    { key: '環境乾淨', icon: '✨' },
    { key: '店員親切', icon: '😊' },
    { key: '品項齊全', icon: '📦' },
    { key: '攻略豐富', icon: '📋' },
    { key: '交通方便', icon: '🚗' },
    { key: '願意再訪', icon: '🔄' },
]

/** 硬體設施標籤（群眾回報） */
const FACILITY_TAGS = [
    { key: '冷氣', icon: '❄️' },
    { key: '廁所', icon: '🚻' },
    { key: '座位', icon: '💺' },
    { key: 'Wi-Fi', icon: '📶' },
    { key: '無障礙', icon: '♿' },
    { key: '電子支付', icon: '💳' },
    { key: '攻略', icon: '📋' },
    { key: '挑號', icon: '🔢' },
    { key: '刮板', icon: '🪣' },
    { key: '放大鏡', icon: '🔍' },
    { key: '老花眼鏡', icon: '👓' },
    { key: '報紙', icon: '📰' },
    { key: '運彩轉播', icon: '📺' },
]

interface RatingPanelProps {
    retailerId: number
    retailerName: string
    onClose: () => void
    onSubmitted?: () => void
}

export default function RatingPanel({ retailerId, retailerName, onClose, onSubmitted }: RatingPanelProps) {
    const { isLoggedIn, loginWithLine } = useAuth()
    const [rating, setRating] = useState(0)
    const [hoverRating, setHoverRating] = useState(0)
    const [selectedServiceTags, setSelectedServiceTags] = useState<string[]>([])
    const [selectedFacilityTags, setSelectedFacilityTags] = useState<string[]>([])
    const [comment, setComment] = useState('')
    const [submitting, setSubmitting] = useState(false)
    const [error, setError] = useState('')
    const [success, setSuccess] = useState(false)

    /** 切換標籤選取 */
    function toggleTag(tag: string, type: 'service' | 'facility') {
        if (type === 'service') {
            setSelectedServiceTags(prev =>
                prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
            )
        } else {
            setSelectedFacilityTags(prev =>
                prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
            )
        }
    }

    /** 送出評分 */
    async function handleSubmit() {
        if (rating === 0) {
            setError('請選擇星等')
            return
        }
        setSubmitting(true)
        setError('')

        try {
            // 嘗試取得 GPS
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
                    // GPS 失敗不阻止
                }
            }

            await submitRating({
                retailerId,
                rating,
                serviceTags: selectedServiceTags,
                facilityTags: selectedFacilityTags,
                comment,
                lat,
                lng,
            })

            setSuccess(true)
            onSubmitted?.()
            setTimeout(onClose, 1500)
        } catch (err: unknown) {
            if (err && typeof err === 'object' && 'response' in err) {
                const axiosErr = err as { response?: { data?: { detail?: string } } }
                setError(axiosErr.response?.data?.detail || '評分失敗')
            } else {
                setError('評分失敗，請稍後再試')
            }
        } finally {
            setSubmitting(false)
        }
    }

    // 未登入：提示登入
    if (!isLoggedIn) {
        return (
            <div className="rating-panel__overlay" onClick={onClose}>
                <div className="rating-panel" onClick={e => e.stopPropagation()}>
                    <button className="rating-panel__close" onClick={onClose}>
                        <X size={20} />
                    </button>
                    <div className="rating-panel__login-prompt">
                        <h3>🔒 請先登入</h3>
                        <p>登入 LINE 以維持評分公正性</p>
                        <button className="rating-panel__line-btn" onClick={loginWithLine}>
                            LINE 登入
                        </button>
                    </div>
                </div>
            </div>
        )
    }

    return (
        <div className="rating-panel__overlay" onClick={onClose}>
            <div className="rating-panel" onClick={e => e.stopPropagation()}>
                <button className="rating-panel__close" onClick={onClose}>
                    <X size={20} />
                </button>

                {success ? (
                    <div className="rating-panel__success">
                        <span className="rating-panel__success-icon">🎉</span>
                        <h3>感謝您的評分！</h3>
                        <p>+20 Karma 積分</p>
                    </div>
                ) : (
                    <>
                        <h3 className="rating-panel__title">評分「{retailerName}」</h3>

                        {/* 星等評分 */}
                        <div className="rating-panel__stars">
                            {[1, 2, 3, 4, 5].map(n => (
                                <button
                                    key={n}
                                    className={`rating-panel__star ${n <= (hoverRating || rating) ? 'rating-panel__star--active' : ''}`}
                                    onMouseEnter={() => setHoverRating(n)}
                                    onMouseLeave={() => setHoverRating(0)}
                                    onClick={() => setRating(n)}
                                >
                                    <Star size={32} fill={n <= (hoverRating || rating) ? '#d4af37' : 'none'} />
                                </button>
                            ))}
                            <span className="rating-panel__rating-text">
                                {rating > 0 ? `${rating} 星` : '點擊評分'}
                            </span>
                        </div>

                        {/* 服務品質標籤 */}
                        <div className="rating-panel__section">
                            <h4>📌 服務品質</h4>
                            <div className="rating-panel__tags">
                                {SERVICE_TAGS.map(({ key, icon }) => (
                                    <button
                                        key={key}
                                        className={`rating-panel__tag ${selectedServiceTags.includes(key) ? 'rating-panel__tag--active' : ''}`}
                                        onClick={() => toggleTag(key, 'service')}
                                    >
                                        {icon} {key}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* 硬體設施（群眾回報） */}
                        <div className="rating-panel__section">
                            <h4>🏪 硬體設施 <span className="rating-panel__crowd-badge">群眾回報</span></h4>
                            <div className="rating-panel__tags">
                                {FACILITY_TAGS.map(({ key, icon }) => (
                                    <button
                                        key={key}
                                        className={`rating-panel__tag ${selectedFacilityTags.includes(key) ? 'rating-panel__tag--active' : ''}`}
                                        onClick={() => toggleTag(key, 'facility')}
                                    >
                                        {icon} {key}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* 文字評論 */}
                        <div className="rating-panel__section">
                            <h4>💬 留下一句話（選填）</h4>
                            <textarea
                                className="rating-panel__comment"
                                placeholder="分享您的經驗..."
                                value={comment}
                                onChange={e => setComment(e.target.value)}
                                maxLength={200}
                                rows={3}
                            />
                            <span className="rating-panel__char-count">{comment.length}/200</span>
                        </div>

                        {error && <p className="rating-panel__error">{error}</p>}

                        <button
                            className="rating-panel__submit"
                            onClick={handleSubmit}
                            disabled={submitting || rating === 0}
                        >
                            {submitting ? '送出中...' : '送出評分'}
                        </button>

                        <p className="rating-panel__hint">
                            <MapPin size={12} /> 系統會自動偵測您的位置做為驗證
                        </p>
                    </>
                )}
            </div>
        </div>
    )
}
