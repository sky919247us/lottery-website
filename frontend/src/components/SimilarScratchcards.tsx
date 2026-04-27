/**
 * 相似刮刮樂推薦（基於獎金結構餘弦相似度）
 * 公開功能，不需登入。
 */
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { fetchSimilarScratchcards, type SimilarResponse } from '../hooks/api'

interface Props {
    scratchcardId: number
    limit?: number
}

export default function SimilarScratchcards({ scratchcardId, limit = 5 }: Props) {
    const [data, setData] = useState<SimilarResponse | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!scratchcardId) return
        setLoading(true)
        fetchSimilarScratchcards(scratchcardId, { limit })
            .then(setData)
            .catch(() => setData(null))
            .finally(() => setLoading(false))
    }, [scratchcardId, limit])

    if (loading) return <div style={{ padding: '1rem', color: '#94a3b8' }}>載入相似款式中...</div>
    if (!data || data.items.length === 0) {
        return (
            <div style={{ padding: '1rem', color: '#64748b', fontSize: '0.9rem' }}>
                目前沒有同價位的歷史款式可比對。
            </div>
        )
    }

    return (
        <section style={{ marginTop: '2rem' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#1e3a8a', marginBottom: '0.5rem' }}>
                <Sparkles size={20} /> 最相似的歷史款式
            </h3>
            <p style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: '0.75rem' }}>
                {data.note}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {data.items.map(it => (
                    <Link
                        key={it.id}
                        to={`/detail/${it.id}`}
                        style={{
                            display: 'flex',
                            gap: '0.75rem',
                            padding: '0.75rem',
                            background: '#fff',
                            border: '1px solid #e2e8f0',
                            borderRadius: 10,
                            textDecoration: 'none',
                            color: 'inherit',
                            alignItems: 'center',
                        }}
                    >
                        {it.imageUrl && (
                            <img src={it.imageUrl} alt={it.name}
                                style={{ width: 56, height: 56, objectFit: 'cover', borderRadius: 6 }} />
                        )}
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem' }}>
                                <strong style={{ color: '#1e3a8a' }}>{it.name}</strong>
                                <span style={{ color: '#10b981', fontWeight: 600, fontSize: '0.9rem' }}>
                                    相似度 {it.similarityPercent}
                                </span>
                            </div>
                            <div style={{ color: '#64748b', fontSize: '0.85rem', marginTop: '0.2rem' }}>
                                完整回收率 {(it.fullReturnRate * 100).toFixed(1)}% · 頭獎倍率 {it.grandPrizeMultiplier.toLocaleString()}x · {it.prizeLevelCount} 層獎
                            </div>
                            {it.reasons.length > 0 && (
                                <div style={{ color: '#475569', fontSize: '0.8rem', marginTop: '0.25rem' }}>
                                    {it.reasons.join('｜')}
                                </div>
                            )}
                        </div>
                    </Link>
                ))}
            </div>
        </section>
    )
}
