/**
 * 玩法資訊面板（AI 解析後的玩法標籤、複雜度、繁中介紹）
 * 公開元件，未解析時顯示提示訊息。
 */
import { useEffect, useState } from 'react'
import { Brain } from 'lucide-react'
import { fetchMechanic, type MechanicResponse } from '../hooks/api'

interface Props {
    scratchcardId: number
}

const TAG_LABELS: Record<string, string> = {
    match3: '三同連線',
    match_any: '任意配對',
    bingo_line: '賓果連線',
    multiplier: '倍數符號',
    bonus_symbol: '特殊符號',
    wild: '萬用符號',
    bonus_game: '額外遊戲',
    lucky_number: '幸運號碼',
    extra_chance: '加碼機會',
    beat_dealer: '比莊家大',
    higher_lower: '比大小',
    sum_target: '加總達標',
    word_game: '文字遊戲',
    crossword: '填字',
    bingo_card: '賓果卡',
    line_match: '連線',
    single_zone: '單區',
    multi_zone: '多區',
    full_board: '全版',
    instant: '刮開即知',
    multi_step: '多步驟',
    compare: '比較式',
    sequence: '序列式',
}

function tagLabel(tag: string) {
    return TAG_LABELS[tag] || tag
}

const RESULT_SPEED_LABEL: Record<string, string> = {
    instant: '刮開即知',
    multi_zone: '多區比對',
    sequence: '依序對獎',
    multi_step: '多步驟',
    compare: '比較式',
}

export default function MechanicPanel({ scratchcardId }: Props) {
    const [data, setData] = useState<MechanicResponse | null>(null)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        if (!scratchcardId) return
        setLoading(true)
        fetchMechanic(scratchcardId)
            .then(setData)
            .finally(() => setLoading(false))
    }, [scratchcardId])

    if (loading) return null
    if (!data) return null

    return (
        <section style={{ marginTop: '1.5rem', padding: '1rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10 }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#1e3a8a', marginBottom: '0.5rem' }}>
                <Brain size={20} /> 玩法解析
            </h3>
            {data.aiDescription && (
                <p style={{ color: '#334155', fontSize: '0.95rem', lineHeight: 1.6, marginBottom: '0.75rem' }}>
                    {data.aiDescription}
                </p>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginBottom: '0.6rem' }}>
                {data.parsedTags.map(t => (
                    <span key={t} style={{
                        padding: '0.2rem 0.6rem', background: '#dbeafe', color: '#1e3a8a',
                        borderRadius: 999, fontSize: '0.8rem', fontWeight: 500,
                    }}>
                        {tagLabel(t)}
                    </span>
                ))}
            </div>
            <div style={{ display: 'flex', gap: '1.2rem', flexWrap: 'wrap', color: '#475569', fontSize: '0.85rem' }}>
                {data.complexityScore > 0 && (
                    <span>複雜度：{'★'.repeat(data.complexityScore)}{'☆'.repeat(Math.max(0, 5 - data.complexityScore))}</span>
                )}
                {data.resultSpeed && (
                    <span>結果：{RESULT_SPEED_LABEL[data.resultSpeed] || data.resultSpeed}</span>
                )}
                {data.parseProvider && (
                    <span style={{ color: '#94a3b8' }}>由 {data.parseProvider} 解析</span>
                )}
            </div>
        </section>
    )
}
