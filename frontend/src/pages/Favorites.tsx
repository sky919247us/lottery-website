/**
 * 收藏清單頁
 * - 顯示登入者收藏的所有刮刮樂
 * - 自動標示停售提醒（距停售或兌獎截止 ≤ 14 天）
 * - 未綁定 LINE 帳號時引導登入
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Heart, AlertTriangle, Clock, Trash2 } from 'lucide-react'
import { useSnackbar } from 'notistack'
import { useAuth } from '../hooks/useAuth'
import { fetchFavorites, removeFavorite, type FavoriteItem } from '../hooks/api'

export default function Favorites() {
    const { isLoggedIn, loading: authLoading, loginWithLine } = useAuth()
    const { enqueueSnackbar } = useSnackbar()
    const [items, setItems] = useState<FavoriteItem[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (authLoading) return
        if (!isLoggedIn) {
            setLoading(false)
            return
        }
        fetchFavorites()
            .then(setItems)
            .catch(() => enqueueSnackbar('載入收藏失敗', { variant: 'error' }))
            .finally(() => setLoading(false))
    }, [isLoggedIn, authLoading])

    async function handleRemove(scratchcardId: number) {
        try {
            await removeFavorite(scratchcardId)
            setItems(prev => prev.filter(it => it.scratchcardId !== scratchcardId))
            enqueueSnackbar('已移除', { variant: 'default' })
        } catch {
            enqueueSnackbar('移除失敗', { variant: 'error' })
        }
    }

    if (authLoading || loading) {
        return <div style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>載入中...</div>
    }

    if (!isLoggedIn) {
        return (
            <div style={{ padding: '3rem 1.5rem', maxWidth: 600, margin: '0 auto', textAlign: 'center' }}>
                <Heart size={48} style={{ color: '#1e3a8a', marginBottom: '1rem' }} />
                <h2 style={{ color: '#1e3a8a', marginBottom: '0.5rem' }}>收藏清單</h2>
                <p style={{ color: '#475569', marginBottom: '1.5rem' }}>
                    收藏與停售提醒功能需綁定 LINE 帳號才能使用。
                </p>
                <button
                    onClick={loginWithLine}
                    style={{
                        padding: '0.75rem 1.5rem',
                        borderRadius: 8,
                        border: 'none',
                        background: '#06c755',
                        color: '#fff',
                        fontWeight: 600,
                        cursor: 'pointer',
                        fontSize: '1rem',
                    }}
                >
                    使用 LINE 登入
                </button>
            </div>
        )
    }

    if (items.length === 0) {
        return (
            <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: '#64748b' }}>
                <Heart size={48} style={{ marginBottom: '1rem' }} />
                <p>還沒有收藏任何款式。在詳情頁點擊「收藏」按鈕加入吧！</p>
                <Link to="/" style={{ color: '#1e3a8a', fontWeight: 600 }}>← 回到首頁瀏覽</Link>
            </div>
        )
    }

    const alertItems = items.filter(it => it.endingSoon || it.redeemingSoon)

    return (
        <div style={{ padding: '1.5rem', maxWidth: 800, margin: '0 auto' }}>
            <h2 style={{ color: '#1e3a8a', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Heart size={24} fill="#ef4444" color="#ef4444" /> 我的收藏
            </h2>
            <p style={{ color: '#64748b', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
                收藏的款式若距停售或兌獎截止 ≤ 14 天，會在下方標示提醒。
            </p>

            {alertItems.length > 0 && (
                <div style={{
                    background: '#fef3c7',
                    border: '1px solid #f59e0b',
                    borderRadius: 8,
                    padding: '0.75rem 1rem',
                    marginBottom: '1rem',
                    color: '#92400e',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                }}>
                    <AlertTriangle size={20} />
                    <span>有 {alertItems.length} 款收藏即將停售或兌獎截止，請留意。</span>
                </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                {items.map(it => (
                    <div
                        key={it.id}
                        style={{
                            background: '#fff',
                            border: it.endingSoon || it.redeemingSoon ? '2px solid #f59e0b' : '1px solid #e2e8f0',
                            borderRadius: 12,
                            padding: '1rem',
                            display: 'flex',
                            gap: '1rem',
                            alignItems: 'center',
                        }}
                    >
                        {it.imageUrl && (
                            <img src={it.imageUrl} alt={it.name}
                                style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 8 }} />
                        )}
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <Link to={`/detail/${it.scratchcardId}`} style={{ color: '#1e3a8a', fontWeight: 600, textDecoration: 'none' }}>
                                {it.name}
                            </Link>
                            <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: '0.25rem' }}>
                                ${it.price} · 銷售率 {it.salesRate || '—'}
                            </div>
                            {it.endingSoon && (
                                <div style={{ fontSize: '0.8rem', color: '#dc2626', marginTop: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                    <Clock size={14} /> 還有 {it.daysToEnd} 天停售（{it.endDate}）
                                </div>
                            )}
                            {it.redeemingSoon && (
                                <div style={{ fontSize: '0.8rem', color: '#dc2626', marginTop: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                    <Clock size={14} /> 還有 {it.daysToRedeemDeadline} 天兌獎截止（{it.redeemDeadline}）
                                </div>
                            )}
                        </div>
                        <button
                            onClick={() => handleRemove(it.scratchcardId)}
                            style={{
                                background: 'transparent',
                                border: '1px solid #cbd5e1',
                                borderRadius: 6,
                                padding: '0.4rem',
                                cursor: 'pointer',
                                color: '#64748b',
                            }}
                            aria-label="移除收藏"
                        >
                            <Trash2 size={16} />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    )
}
