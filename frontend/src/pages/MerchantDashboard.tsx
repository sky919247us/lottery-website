/**
 * 店家管理後台
 *
 * 功能：
 * 1. 認領我的店家（提交申請）
 * 2. 營業狀態即時切換（巨型按鈕）
 * 3. 設施&服務標籤管理
 * 4. 臨時公告發佈
 * 5. Karma 等級顯示
 */
import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
    Store, ToggleLeft, ToggleRight, Shield,
    CheckCircle, Send, Tag, Megaphone, MapPin, Star
} from 'lucide-react'
import {
    fetchRetailers, updateRetailerTags, updateBusinessStatus,
    createAnnouncement, submitMerchantClaim,
    type RetailerData
} from '../hooks/api'
import { useUser } from '../hooks/useUser'
import PlanCard from '../components/PlanCard'
import './MerchantDashboard.css'

/** 設施標籤設定 */
const TAG_CONFIG = [
    { key: 'hasAC', label: '❄️ 冷氣', category: '硬體' },
    { key: 'hasToilet', label: '🚻 廁所', category: '硬體' },
    { key: 'hasSeats', label: '💺 座位', category: '硬體' },
    { key: 'hasWifi', label: '📶 Wi-Fi', category: '硬體' },
    { key: 'hasAccessibility', label: '♿ 無障礙', category: '硬體' },
    { key: 'hasEPay', label: '💳 電子支付', category: '硬體' },
    { key: 'hasStrategy', label: '📋 攻略', category: '專業' },
    { key: 'hasNumberPick', label: '🔢 挑號', category: '專業' },
    { key: 'hasScratchBoard', label: '🪣 刮板', category: '專業' },
    { key: 'hasMagnifier', label: '🔍 放大鏡', category: '專業' },
    { key: 'hasReadingGlasses', label: '👓 老花眼鏡', category: '專業' },
    { key: 'hasNewspaper', label: '📰 明牌報', category: '專業' },
    { key: 'hasSportTV', label: '📺 運彩轉播', category: '專業' },
]

/** Karma 等級色彩 */
const LEVEL_COLORS = [
    '#94a3b8', '#6ee7b7', '#34d399', '#10b981',
    '#f59e0b', '#f97316', '#ef4444', '#dc2626',
    '#a855f7', '#d4af37',
]

export default function MerchantDashboard() {
    const { user } = useUser()
    const [retailers, setRetailers] = useState<RetailerData[]>([])
    const [selectedRetailer, setSelectedRetailer] = useState<RetailerData | null>(null)
    const [claimId, setClaimId] = useState<number | null>(null)
    const [searchTerm, setSearchTerm] = useState('')
    const [step, setStep] = useState<'search' | 'manage'>('search')
    const [tags, setTags] = useState<Record<string, boolean>>({})
    const [announcement, setAnnouncement] = useState('')
    const [saving, setSaving] = useState(false)
    const [message, setMessage] = useState('')

    useEffect(() => {
        fetchRetailers().then(setRetailers).catch(() => { })
    }, [])

    /** 搜尋結果 */
    const searchResults = searchTerm.length >= 2
        ? retailers.filter(r =>
            r.name.includes(searchTerm) || r.address.includes(searchTerm)
        ).slice(0, 20)
        : []

    /** 選擇店家 */
    async function selectRetailer(r: RetailerData) {
        setSelectedRetailer(r)
        setStep('manage')
        // 載入現有標籤
        const currentTags: Record<string, boolean> = {}
        TAG_CONFIG.forEach(t => {
            currentTags[t.key] = (r as any)[t.key] ?? false
        })
        setTags(currentTags)
        setAnnouncement(r.announcement || '')

        // 查詢認領 ID（用於方案卡片）
        if (r.isClaimed) {
            try {
                const res = await fetch(`/api/merchant/retailers/${r.id}/claim`)
                const data = await res.json()
                setClaimId(data.id || null)
            } catch (err) {
                console.error('查詢認領信息失敗:', err)
                setClaimId(null)
            }
        } else {
            setClaimId(null)
        }
    }

    /** 切換營業狀態 */
    async function toggleStatus() {
        if (!selectedRetailer) return
        setSaving(true)
        try {
            await updateBusinessStatus(selectedRetailer.id, !selectedRetailer.isActive)
            setSelectedRetailer({ ...selectedRetailer, isActive: !selectedRetailer.isActive })
            showMessage(selectedRetailer.isActive ? '已設為休息中' : '已開始營業')
        } catch {
            showMessage('操作失敗')
        } finally {
            setSaving(false)
        }
    }

    /** 儲存標籤 */
    async function saveTags() {
        if (!selectedRetailer) return
        setSaving(true)
        try {
            await updateRetailerTags(selectedRetailer.id, tags)
            showMessage('設施標籤已更新！')
        } catch {
            showMessage('儲存失敗')
        } finally {
            setSaving(false)
        }
    }

    /** 發佈公告 */
    async function publishAnnouncement() {
        if (!selectedRetailer || !announcement.trim()) return
        setSaving(true)
        try {
            await createAnnouncement(selectedRetailer.id, announcement)
            showMessage('公告已發佈！')
        } catch {
            showMessage('發佈失敗')
        } finally {
            setSaving(false)
        }
    }

    /** 提交認領 */
    async function handleClaim() {
        if (!selectedRetailer || !user) return
        setSaving(true)
        try {
            await submitMerchantClaim({
                retailerId: selectedRetailer.id,
                userId: user.id,
            })
            showMessage('認領申請已提交，等待管理員審核')
        } catch {
            showMessage('提交失敗，可能已被認領')
        } finally {
            setSaving(false)
        }
    }

    function showMessage(msg: string) {
        setMessage(msg)
        setTimeout(() => setMessage(''), 3000)
    }

    return (
        <div className="merchant container">
            {/* Hero */}
            <section className="merchant__hero">
                <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}>
                    <h1 className="merchant__title">
                        <Store size={32} /> 店家管理後台
                    </h1>
                    <p className="merchant__subtitle">認領你的店家，管理設施標籤與營業狀態</p>
                </motion.div>
            </section>

            {/* 使用者 Karma 資訊 */}
            {user && (
                <motion.div
                    className="merchant__karma-bar glass-card"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                >
                    <div className="merchant__karma-badge" style={{
                        borderColor: LEVEL_COLORS[user.karmaLevel - 1]
                    }}>
                        <Star size={16} style={{ color: LEVEL_COLORS[user.karmaLevel - 1] }} />
                        <span>Lv.{user.karmaLevel}</span>
                    </div>
                    <div>
                        <strong>{user.levelTitle}</strong>
                        <span className="merchant__karma-points">{user.karmaPoints} 積分</span>
                    </div>
                    <div className="merchant__karma-progress">
                        <div className="merchant__karma-fill" style={{
                            width: `${Math.min(100, (user.karmaPoints / user.nextLevelPoints) * 100)}%`,
                            background: LEVEL_COLORS[user.karmaLevel - 1],
                        }} />
                    </div>
                </motion.div>
            )}

            {/* 訊息提示 */}
            {message && (
                <motion.div
                    className="merchant__toast"
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                >
                    <CheckCircle size={16} /> {message}
                </motion.div>
            )}

            {step === 'search' && (
                <motion.section
                    className="merchant__search-section"
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
                >
                    <h2>🔍 搜尋你的店家</h2>
                    <input
                        className="merchant__search-input"
                        type="text"
                        placeholder="輸入店名或地址（至少 2 個字）..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                    />
                    {searchResults.length > 0 && (
                        <div className="merchant__search-results">
                            {searchResults.map(r => (
                                <div
                                    key={r.id}
                                    className="merchant__search-item glass-card"
                                    onClick={() => selectRetailer(r)}
                                >
                                    <div className="merchant__search-name">
                                        <Store size={16} /> {r.name}
                                        {r.isClaimed && <span className="merchant__claimed-badge">已認領</span>}
                                    </div>
                                    <div className="merchant__search-address">
                                        <MapPin size={14} /> {r.address}
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </motion.section>
            )}

            {step === 'manage' && selectedRetailer && (
                <motion.div
                    className="merchant__dashboard"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                >
                    {/* 店家資訊 */}
                    <div className="merchant__store-info glass-card">
                        <div className="merchant__store-header">
                            <h2>{selectedRetailer.name}</h2>
                            <button className="merchant__back-btn" onClick={() => setStep('search')}>
                                ← 重新選擇
                            </button>
                        </div>
                        <p><MapPin size={14} /> {selectedRetailer.address}</p>
                        <p className="merchant__store-source">
                            {selectedRetailer.source === '台灣彩券' ? '🎫' : '⚽'} {selectedRetailer.source}
                        </p>
                    </div>

                    {/* 認領按鈕 */}
                    {!selectedRetailer.isClaimed && (
                        <div className="merchant__claim-section glass-card">
                            <h3><Shield size={18} /> 認領此店家</h3>
                            <p>認領後即可管理營業狀態、設施標籤與庫存。認領需管理員審核。</p>
                            <button
                                className="merchant__claim-btn"
                                onClick={handleClaim}
                                disabled={saving || !user}
                            >
                                <Shield size={16} /> 提交認領申請
                            </button>
                        </div>
                    )}

                    {/* 方案卡片 */}
                    {selectedRetailer.isClaimed && user && (
                        <PlanCard
                            claimId={claimId}
                            retailerId={selectedRetailer.id}
                            userId={user.id}
                        />
                    )}

                    <div className="merchant__panels">
                        {/* 營業狀態 */}
                        <div className="merchant__panel glass-card">
                            <h3>營業狀態</h3>
                            <button
                                className={`merchant__status-toggle ${selectedRetailer.isActive ? 'merchant__status-toggle--open' : 'merchant__status-toggle--closed'}`}
                                onClick={toggleStatus}
                                disabled={saving}
                            >
                                {selectedRetailer.isActive ? (
                                    <><ToggleRight size={32} /> 營業中</>
                                ) : (
                                    <><ToggleLeft size={32} /> 休息中</>
                                )}
                            </button>
                        </div>

                        {/* 臨時公告 */}
                        <div className="merchant__panel glass-card">
                            <h3><Megaphone size={18} /> 臨時公告</h3>
                            <textarea
                                className="merchant__announcement-input"
                                placeholder="例：初三不休息、新到 2000 元刮刮樂..."
                                value={announcement}
                                onChange={(e) => setAnnouncement(e.target.value)}
                                maxLength={200}
                            />
                            <button
                                className="merchant__save-btn"
                                onClick={publishAnnouncement}
                                disabled={saving || !announcement.trim()}
                            >
                                <Send size={14} /> 發佈公告
                            </button>
                        </div>
                    </div>

                    {/* 設施標籤 */}
                    <div className="merchant__tags-section glass-card">
                        <h3><Tag size={18} /> 設施與服務標籤</h3>
                        <div className="merchant__tags-grid">
                            {['硬體', '專業'].map(cat => (
                                <div key={cat} className="merchant__tags-group">
                                    <h4>{cat === '硬體' ? '🏪 硬體設施' : '🎯 專業服務'}</h4>
                                    {TAG_CONFIG.filter(t => t.category === cat).map(t => (
                                        <label key={t.key} className="merchant__tag-toggle">
                                            <input
                                                type="checkbox"
                                                checked={tags[t.key] || false}
                                                onChange={() => setTags({ ...tags, [t.key]: !tags[t.key] })}
                                            />
                                            <span>{t.label}</span>
                                        </label>
                                    ))}
                                </div>
                            ))}
                        </div>
                        <button
                            className="merchant__save-btn"
                            onClick={saveTags}
                            disabled={saving}
                        >
                            <CheckCircle size={14} /> 儲存標籤
                        </button>
                    </div>
                </motion.div>
            )}
        </div>
    )
}
