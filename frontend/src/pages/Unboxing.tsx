/**
 * 大樣本統計 — 列表頁
 *
 * 一列一款的緊湊表格，款式數量成長也只是往下長，不會爆版。
 * 逐張序號屬於分級資料，這一頁只呈現彙總，全部公開。
 */
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { BarChart3, ArrowUpDown, Youtube } from 'lucide-react'
import SeoHead from '../components/SeoHead'
import { fetchUnboxingGames, fetchUnboxingSummary } from '../hooks/api'
import type { UnboxingGameItem } from '../hooks/api'
import './Unboxing.css'

type SortKey = 'gameId' | 'returnRate' | 'bookCount' | 'price' | 'winRate'

const nf = (n: number) => n.toLocaleString('en-US')
const pc = (x: number | null | undefined, d = 1) =>
    x === null || x === undefined ? '—' : `${(x * 100).toFixed(d)}%`

export default function Unboxing() {
    const [sortKey, setSortKey] = useState<SortKey>('gameId')
    const [asc, setAsc] = useState(false)

    const { data: summary } = useQuery({
        queryKey: ['unboxingSummary'],
        queryFn: fetchUnboxingSummary,
        staleTime: 10 * 60 * 1000,
    })
    const { data: games, isLoading } = useQuery({
        queryKey: ['unboxingGames'],
        queryFn: () => fetchUnboxingGames('desc'),
        staleTime: 10 * 60 * 1000,
    })

    const rows = useMemo(() => {
        if (!games) return []
        const val = (g: UnboxingGameItem) =>
            sortKey === 'gameId' ? Number(g.gameId) || 0 : (g[sortKey] as number)
        return [...games].sort((a, b) => (asc ? val(a) - val(b) : val(b) - val(a)))
    }, [games, sortKey, asc])

    const toggle = (k: SortKey) => {
        if (k === sortKey) setAsc(!asc)
        else {
            setSortKey(k)
            setAsc(false)
        }
    }

    const th = (k: SortKey, label: string) => (
        <th className="ub-th-sort" onClick={() => toggle(k)}>
            {label}
            <ArrowUpDown size={11} className={sortKey === k ? 'ub-sort-on' : 'ub-sort-off'} />
        </th>
    )

    return (
        <div className="ub container">
            <SeoHead
                title="大樣本統計 — 整本刮刮樂實測回本率資料庫"
                description="刮刮研究室把每一支整本開箱影片的逐張中獎資料結構化公開：實測回本率、中獎率、每本獎項分佈，與官方派彩率逐款對照。只講數據。"
                path="/unboxing"
            />

            <header className="ub__head">
                <h1>
                    <BarChart3 size={24} /> 大樣本統計
                </h1>
                <p>
                    我們把每一支「包本解密」影片刮完的每一張都記下來，攤在這裡讓你自己驗算。
                    樣本夠大時，實測數字會非常接近官方派彩率——這正是這個頁面存在的意義。
                </p>
            </header>

            {summary && (
                <div className="ub__kpi">
                    {[
                        ['累計款式', `${summary.gameCount} 款`],
                        ['累計本數', `${summary.bookCount} 本`],
                        ['累計張數', nf(summary.ticketCount)],
                        ['總投入', `$${nf(summary.totalCost)}`],
                        ['總回收', `$${nf(summary.totalPrize)}`],
                        ['實測回本率', pc(summary.returnRate)],
                    ].map(([label, value], i) => (
                        <div className="ub__kpi-cell" key={label}>
                            <span>{label}</span>
                            <strong className={i === 5 ? 'ub-accent' : ''}>{value}</strong>
                        </div>
                    ))}
                </div>
            )}

            {isLoading ? (
                <p className="ub__empty">載入中…</p>
            ) : !rows.length ? (
                <p className="ub__empty">尚無開箱資料</p>
            ) : (
                <div className="ub__table-wrap">
                    <table className="ub__table">
                        <thead>
                            <tr>
                                {th('gameId', '款式')}
                                {th('price', '單價')}
                                <th>張/本</th>
                                {th('bookCount', '本數')}
                                <th>張數</th>
                                <th>批次</th>
                                <th>投入</th>
                                <th>回收</th>
                                {th('returnRate', '實測回本率')}
                                <th>官方派彩率</th>
                                <th>差距</th>
                                {th('winRate', '實測中獎率')}
                                <th>官方中獎率</th>
                                <th>最大單張</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((g) => (
                                <tr key={g.gameId}>
                                    <td className="ub-sticky">
                                        <Link to={`/unboxing/${g.gameId}`} className="ub__name-link">
                                            <span className="ub__name">{g.name || g.gameId}</span>
                                            <span className="ub__no">
                                                NO. {g.gameId}
                                                {g.videoCount > 0 && <Youtube size={11} />}
                                            </span>
                                        </Link>
                                    </td>
                                    <td>${g.price}</td>
                                    <td>{g.ticketsPerBook}</td>
                                    <td>
                                        {g.bookCount}
                                        {g.bookCount < 3 && <em className="ub__weak">・樣本少</em>}
                                    </td>
                                    <td>{nf(g.ticketCount)}</td>
                                    <td>{g.batchCount || '—'}</td>
                                    <td>${nf(g.cost)}</td>
                                    <td>${nf(g.totalPrize)}</td>
                                    <td
                                        className={
                                            g.officialReturnRate
                                                ? g.returnRate >= g.officialReturnRate
                                                    ? 'text-green'
                                                    : 'text-red'
                                                : ''
                                        }
                                    >
                                        <strong>{pc(g.returnRate)}</strong>
                                    </td>
                                    <td>{pc(g.officialReturnRate)}</td>
                                    <td
                                        className={
                                            g.returnRateDelta === null
                                                ? ''
                                                : g.returnRateDelta >= 0
                                                  ? 'text-green'
                                                  : 'text-red'
                                        }
                                    >
                                        {g.returnRateDelta === null
                                            ? '—'
                                            : `${g.returnRateDelta >= 0 ? '+' : ''}${(g.returnRateDelta * 100).toFixed(1)}pp`}
                                    </td>
                                    <td>{pc(g.winRate)}</td>
                                    <td>{pc(g.officialWinRate, 2)}</td>
                                    <td>${nf(g.maxPrizeHit)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <p className="ub__disclaimer">
                <strong>資料說明</strong>：以上皆為刮刮研究室實際購買並逐張刮開的紀錄，
                「官方派彩率」由台彩公布的獎金結構換算。實測樣本不等於母體，
                每張刮刮樂彼此獨立，<strong>過往數據無法預測未來</strong>。
                本站資料僅供娛樂與研究，不構成任何投注建議。
            </p>
        </div>
    )
}
