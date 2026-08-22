/**
 * 大樣本統計 — 單款詳情頁
 *
 * 版面：常駐頁首（期數／款名／核心數字／影片封面）+ 4 個分頁籤，
 * 不做一頁到底，否則款式與本數一多就又長又寬。
 *
 * 分級：逐張序號由後端依 accessLevel 決定給不給，前端只負責畫對應的引導。
 * 注意前台沒有全域 auth context，必須等 useAuth().loading 結束再發請求，
 * 否則 axios 的 Authorization header 還沒設好，會被當成未登入拿到 T0 資料。
 */
import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Lock, Play } from 'lucide-react'
import SeoHead from '../components/SeoHead'
import PrizeStructureTable from '../components/PrizeStructureTable'
import { useAuth } from '../hooks/useAuth'
import { fetchUnboxingDetail } from '../hooks/api'
import type { UnboxingBookRow } from '../hooks/api'
import { heatmapColumns } from '../utils/scratchcard'
import {
    cumulativeNet,
    median,
    percentileOf,
    positionOutliers,
    simulateDraws,
    stdDev,
    thirds,
} from '../utils/unboxingStats'
import './Unboxing.css'

const nf = (n: number) => Math.round(n).toLocaleString('en-US')
const pc = (x: number | null | undefined, d = 1) =>
    x === null || x === undefined ? '—' : `${(x * 100).toFixed(d)}%`

/** 獎金級距配色：由淺綠到深紅，金額越大越醒目 */
const RAMP = ['#bcd9c4', '#8cc4a0', '#5fae7d', '#f0c36a', '#e08a3c', '#c0392b', '#7b241c']

function colorFor(amount: number, tiers: number[]): string {
    const idx = tiers.indexOf(amount)
    if (idx < 0) return '#7b241c'
    return RAMP[Math.min(RAMP.length - 1, idx)]
}

export default function UnboxingDetail() {
    const { gameId = '' } = useParams<{ gameId: string }>()
    const { isLoggedIn, loading: authLoading, loginWithLine } = useAuth()
    const [tab, setTab] = useState(0)
    const [drawN, setDrawN] = useState(50)
    const [simSeed, setSimSeed] = useState(0)
    const [myWin, setMyWin] = useState('')

    const { data, isLoading } = useQuery({
        queryKey: ['unboxingDetail', gameId, isLoggedIn],
        queryFn: () => fetchUnboxingDetail(gameId),
        // 等身分確定後再打，避免拿到權限不足的版本
        enabled: !authLoading && !!gameId,
        staleTime: 5 * 60 * 1000,
    })

    const tiers = useMemo(() => {
        if (!data) return []
        return Object.keys(data.measured.prizeCounts)
            .map(Number)
            .sort((a, b) => a - b)
    }, [data])

    const pool = useMemo(() => {
        if (!data) return []
        return data.books.flatMap((b) => b.prizes || [])
    }, [data])

    const sim = useMemo(() => {
        if (!pool.length) return null
        return simulateDraws(pool, drawN, data!.price, 5000)
        // simSeed 只是用來讓使用者按「重新模擬」時重跑
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [pool, drawN, simSeed, data?.price])

    if (authLoading || isLoading) return <p className="ub__empty">載入中…</p>
    if (!data) return <p className="ub__empty">查無此款的開箱資料</p>

    const m = data.measured
    const session = data.sessions.find((s) => s.videoId) || data.sessions[0]
    const cols = heatmapColumns(data.ticketsPerBook)
    const sorted = [...data.books].sort((a, b) => b.totalPrize - a.totalPrize)

    const loginPrompt = (title: string, desc: string) => (
        <div className="ub__lock">
            <strong>
                <Lock size={14} /> {title}
            </strong>
            {desc}
            <br />
            <button className="ub__lock-btn" onClick={loginWithLine}>
                使用 LINE 登入
            </button>
        </div>
    )

    const levelPrompt = (title: string, desc: string) => (
        <div className="ub__lock">
            <strong>
                <Lock size={14} /> {title}
            </strong>
            {desc}
            <br />
            <Link className="ub__lock-btn ub__lock-btn--level" to="/levels">
                看看怎麼升到 Lv.{data.requiredLevelForFull}
            </Link>
        </div>
    )

    const gate = (need: 1 | 2, node: React.ReactNode) => {
        if (data.accessLevel >= need) return node
        if (need === 1) {
            return loginPrompt(
                '每本明細需登入 LINE 帳號',
                '登入後可看到每一本的回本金額、中獎張數、槓龜張數與各獎項張數。',
            )
        }
        return levelPrompt(
            `逐張序號需 Lv.${data.requiredLevelForFull}「刮刮研究室研究員」`,
            '升級後可看到每一本的完整流水序號與逐張中獎序列，並可匯出 CSV。',
        )
    }

    /* ---------- 總覽 ---------- */
    const overview = () => {
        const totals = m.bookTotals
        const sd = stdDev(totals)
        // 「大獎」＝不是每本都會有的級距（實測每本 < 0.5 張）。
        // 直接拿最大級距當大獎會出錯：5151 每本固定 2 張 $5,000，那是保底不是大獎。
        const rareTiers = tiers.filter(
            (t) => (m.prizeCounts[String(t)] || 0) / (m.bookCount || 1) < 0.5,
        )
        const rareAmount = rareTiers.reduce(
            (a, t) => a + t * (m.prizeCounts[String(t)] || 0),
            0,
        )
        const rareHits = rareTiers.reduce((a, t) => a + (m.prizeCounts[String(t)] || 0), 0)
        const withoutBig = m.cost ? (m.totalPrize - rareAmount) / m.cost : 0
        const over100 = totals.filter((t) => t >= data.ticketsPerBook * data.price).length
        const seg = thirds([m.positionPrize])
        const out = positionOutliers(m.positionWins, m.bookCount, m.winRate)

        // 官方派彩率含了頭獎那種「這個樣本規模幾乎不可能中到」的獎項，
        // 直接拿實測去比會系統性偏低。算出扣掉那些獎之後的「可及派彩率」才是公平的比較基準。
        const op = data.official.prizes
        const totalPayout = op.reduce((a, p) => a + p.prizeAmount * p.totalCount, 0)
        const unreachable = op.filter(
            (p) =>
                data.totalIssued > 0 &&
                (p.totalCount / data.totalIssued) * m.ticketCount < 1,
        )
        const unreachableShare = totalPayout
            ? unreachable.reduce((a, p) => a + p.prizeAmount * p.totalCount, 0) / totalPayout
            : 0
        const reachable = data.official.returnRate
            ? data.official.returnRate * (1 - unreachableShare)
            : null
        const cards: [string, string][] = [
            [
                '實測 vs 官方',
                data.official.returnRate
                    ? `${m.bookCount} 本實測回本率 ${pc(m.returnRate)}，官方派彩率 ${pc(data.official.returnRate)}，差 ${((m.returnRate - data.official.returnRate) * 100).toFixed(1)}pp。樣本越大越會貼上官方數字。`
                    : `實測回本率 ${pc(m.returnRate)}。官方派彩率待獎金結構補齊後自動比對。`,
            ],
            [
                '公平比較基準',
                reachable && unreachableShare > 0.01
                    ? `官方派彩率有 ${pc(unreachableShare)} 來自這 ${nf(m.ticketCount)} 張規模幾乎碰不到的大獎（期望不足 1 張），扣掉後的「可及派彩率」是 ${pc(reachable)}。實測 ${pc(m.returnRate)} 與它相差 ${((m.returnRate - reachable) * 100).toFixed(1)}pp —— 這才是公平的比較。`
                    : reachable
                      ? `這款的派彩幾乎都集中在小獎，${nf(m.ticketCount)} 張的樣本已能涵蓋絕大多數獎項級距，可以直接跟官方派彩率比。`
                      : '待官方獎金結構補齊後計算。',
            ],
            [
                '本間變異',
                `每本合計獎金中位數 $${nf(median(totals))}，標準差 $${nf(sd)}，最高 $${nf(Math.max(...totals))}、最低 $${nf(Math.min(...totals))}。變異多半來自有沒有中到大獎。`,
            ],
            [
                '回本門檻機率',
                `${m.bookCount} 本裡，整本回本（回本率 ≥ 100%）的有 ${over100} 本，占 ${pc(over100 / (m.bookCount || 1))}。`,
            ],
            [
                '排除大獎回本率',
                rareTiers.length
                    ? `扣掉 ${rareHits} 張「不是每本都有」的大獎（${rareTiers.map((t) => `$${nf(t)}`).join('、')}）後，回本率降到 ${pc(withoutBig)}，這是這款的「小獎體質」。`
                    : '這款樣本裡每個獎項級距每本平均都出現 0.5 張以上，沒有靠單張大獎撐盤。',
            ],
            [
                '前中後段表現',
                `全部 ${m.bookCount} 本合計：前 1/3 回收 $${nf(seg[0])}、中 1/3 $${nf(seg[1])}、後 1/3 $${nf(seg[2])}。大獎並沒有特別藏在後段。`,
            ],
            [
                '張號位置檢定',
                `各張號中獎次數的 95% 區間為 ${m.positionWins.length ? `${out.low.toFixed(1)}～${out.high.toFixed(1)}` : '—'}，實際落在區間外的有 ${out.outliers} 個張號，隨機情況下本來就約有 ${out.expectedOutliers.toFixed(1)} 個。沒有「哪一張比較會中」這回事。`,
            ],
        ]
        return (
            <>
                <div className="ub__cards">
                    {cards.map(([t, d]) => (
                        <div className="ub__card" key={t}>
                            <b>{t}</b>
                            <p>{d}</p>
                        </div>
                    ))}
                </div>

                <h2 className="ub__section-title">官方獎金結構對照</h2>
                <PrizeStructureTable
                    prizes={data.official.prizes.map((p) => ({
                        prizeName: p.prizeName,
                        prizeAmount: p.prizeAmount,
                        totalCount: p.totalCount,
                        perBookDesc: p.perBookDesc,
                    }))}
                    showRemaining={false}
                    showPerBook
                    totalIssued={data.totalIssued}
                    ticketsPerBook={data.ticketsPerBook}
                    measuredCounts={m.prizeCounts}
                    measuredBookCount={m.bookCount}
                />
                <p className="ub__note">
                    「理論每本」＝該獎項總張數 ÷ 發行張數 × 每本張數；「實測每本」為 {m.bookCount} 本的平均。兩者接近代表樣本已足夠有代表性。
                </p>

                <h2 className="ub__section-title">買 N 張模擬器</h2>
                {pool.length ? (
                    <>
                        <div className="ub__sim">
                            <span>隨機抽</span>
                            <input
                                type="number"
                                min={1}
                                max={pool.length}
                                value={drawN}
                                onChange={(e) => setDrawN(Math.max(1, Number(e.target.value) || 1))}
                            />
                            <span>張，跑 5,000 次</span>
                            <button onClick={() => setSimSeed(simSeed + 1)}>重新模擬</button>
                        </div>
                        {sim && (
                            <div className="ub__cards">
                                <div className="ub__card">
                                    <b>回本機率</b>
                                    <p>{pc(sim.breakEvenRate)}（淨損益 ≥ 0 的比例）</p>
                                </div>
                                <div className="ub__card">
                                    <b>中位數損益</b>
                                    <p>
                                        {sim.medianNet >= 0 ? '+' : ''}
                                        {nf(sim.medianNet)} 元
                                    </p>
                                </div>
                                <div className="ub__card">
                                    <b>最好 / 最壞</b>
                                    <p>
                                        +{nf(sim.best)} 元 / {nf(sim.worst)} 元
                                    </p>
                                </div>
                            </div>
                        )}
                        <p className="ub__note">
                            這是對「已實測的這批獎項分佈」做放回抽樣，回答的是
                            「照這批資料的體質，隨機買 N 張會怎樣」，
                            <strong>不是預測未來</strong>。
                        </p>
                    </>
                ) : (
                    levelPrompt(
                        `模擬器需 Lv.${data.requiredLevelForFull}`,
                        '模擬需要逐張資料，升級後即可使用。',
                    )
                )}

                <h2 className="ub__section-title">我的一本對照</h2>
                <div className="ub__sim">
                    <span>我這本總共中了</span>
                    <input
                        type="number"
                        value={myWin}
                        onChange={(e) => setMyWin(e.target.value)}
                        placeholder="金額"
                    />
                    <span>元</span>
                </div>
                {myWin !== '' && (
                    <p className="ub__note">
                        你這本贏過我們實測 {m.bookCount} 本中的{' '}
                        <strong>{pc(percentileOf(m.bookTotals, Number(myWin) || 0))}</strong>，
                        回本率 {pc((Number(myWin) || 0) / (data.ticketsPerBook * data.price))}。
                    </p>
                )}
            </>
        )
    }

    /* ---------- 每本明細 ---------- */
    const bookTable = (rows: UnboxingBookRow[]) => (
        <>
            <div className="ub__table-wrap" style={{ maxHeight: 340, overflowY: 'auto' }}>
                <table className="ub__table">
                    <thead>
                        <tr>
                            <th className="ub-sticky">流水序號</th>
                            <th>批次</th>
                            <th>回本金額</th>
                            <th>回本率</th>
                            <th>中獎</th>
                            <th>槓龜</th>
                            <th>最長槓龜</th>
                            {tiers.map((t) => (
                                <th key={t}>${nf(t)}</th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((b) => (
                            <tr key={b.id}>
                                <td className="ub-sticky ub__no">{b.label}</td>
                                <td>{b.batchKey}</td>
                                <td>${nf(b.totalPrize)}</td>
                                <td
                                    className={
                                        !data.official.returnRate
                                            ? ''
                                            : b.returnRate >= data.official.returnRate
                                              ? 'text-green'
                                              : 'text-red'
                                    }
                                >
                                    {pc(b.returnRate)}
                                </td>
                                <td>{b.winCount}</td>
                                <td>{b.missCount}</td>
                                <td>{b.maxDryRun}</td>
                                {tiers.map((t) => (
                                    <td key={t}>{b.prizeCounts[String(t)] || '·'}</td>
                                ))}
                            </tr>
                        ))}
                    </tbody>
                    <tfoot>
                        <tr>
                            <td className="ub-sticky">合計 / 平均</td>
                            <td>{m.batchCount} 批</td>
                            <td>${nf(m.totalPrize)}</td>
                            <td>{pc(m.returnRate)}</td>
                            <td>{rows.reduce((a, b) => a + b.winCount, 0)}</td>
                            <td>{rows.reduce((a, b) => a + b.missCount, 0)}</td>
                            <td>{Math.max(...rows.map((b) => b.maxDryRun))}</td>
                            {tiers.map((t) => (
                                <td key={t}>{m.prizeCounts[String(t)] || 0}</td>
                            ))}
                        </tr>
                    </tfoot>
                </table>
            </div>
            <p className="ub__note">
                依回本金額由高到低排序。
                {data.accessLevel < 2
                    ? `流水序號已部分遮蔽，Lv.${data.requiredLevelForFull} 可見完整序號。`
                    : '批次由流水序號連號自動分群 —— 連號多半是同一箱進貨，但不見得同一家店。'}
            </p>
        </>
    )

    /* ---------- 熱力圖 ---------- */
    const heatmap = () => {
        const maxAgg = Math.max(...m.positionWins, 1)
        return (
            <>
                <p className="ub__note" style={{ marginTop: 0 }}>
                    <strong>聚合熱力圖</strong>：{m.bookCount} 本疊起來，每格顏色代表該張號在所有本中中了幾次
                    （0～{maxAgg}）。一張圖取代 {m.bookCount} 張。
                </p>
                <div className="ub__heat-row">
                    <div className="ub__heat-label">全 {m.bookCount} 本</div>
                    <div
                        className="ub__heat-grid"
                        style={{ gridTemplateColumns: `repeat(${cols}, 13px)`, ['--ub-cols' as string]: cols }}
                    >
                        {m.positionWins.map((c, i) => (
                            <div
                                key={i}
                                className="ub__heat-cell"
                                title={`第 ${i + 1} 張：${m.bookCount} 本中中了 ${c} 次`}
                                style={
                                    c
                                        ? { background: `rgba(11,25,44,${0.15 + (c / maxAgg) * 0.85})` }
                                        : undefined
                                }
                            />
                        ))}
                    </div>
                </div>

                <h2 className="ub__section-title">逐本熱力圖</h2>
                {gate(
                    2,
                    <>
                        <div className="ub__heat-box">
                            {data.books.map((b) => (
                                <div className="ub__heat-row" key={b.id}>
                                    <div className="ub__heat-label">{b.label}</div>
                                    <div
                                        className="ub__heat-grid"
                                        style={{ gridTemplateColumns: `repeat(${cols}, 13px)`, ['--ub-cols' as string]: cols }}
                                    >
                                        {(b.prizes || []).map((v, i) => (
                                            <div
                                                key={i}
                                                className="ub__heat-cell"
                                                title={`第 ${i + 1} 張 ${v ? `$${nf(v)}` : '槓龜'}`}
                                                style={
                                                    v ? { background: colorFor(v, tiers) } : undefined
                                                }
                                            />
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                        <div className="ub__heat-legend">
                            {tiers.map((t) => (
                                <span key={t}>
                                    <i
                                        className="ub__swatch"
                                        style={{ background: colorFor(t, tiers) }}
                                    />
                                    ${nf(t)}
                                </span>
                            ))}
                            <span>
                                <i
                                    className="ub__swatch"
                                    style={{ background: '#eef2f6', border: '1px solid #e2e8f0' }}
                                />
                                槓龜
                            </span>
                            <span>每列 {cols} 張，滑鼠移上可看第幾張</span>
                        </div>
                    </>,
                )}
            </>
        )
    }

    /* ---------- 原始資料 ---------- */
    const raw = () => {
        const exportCsv = () => {
            const head = '流水序號,批次,張號,獎金\n'
            const body = data.books
                .flatMap((b) =>
                    (b.prizes || []).map(
                        (v, i) => `${b.serialNo || b.label},${b.batchKey},${i + 1},${v}`,
                    ),
                )
                .join('\n')
            const blob = new Blob(['﻿' + head + body], { type: 'text/csv;charset=utf-8' })
            const a = document.createElement('a')
            a.href = URL.createObjectURL(blob)
            a.download = `unboxing_${gameId}.csv`
            a.click()
            URL.revokeObjectURL(a.href)
        }
        return (
            <>
                <div className="ub__sim">
                    <button onClick={exportCsv}>下載 CSV</button>
                    <span className="ub__note" style={{ margin: 0 }}>
                        共 {nf(m.ticketCount)} 筆逐張紀錄
                    </span>
                </div>
                <div className="ub__table-wrap" style={{ maxHeight: 420, overflowY: 'auto' }}>
                    <table className="ub__table">
                        <thead>
                            <tr>
                                <th className="ub-sticky">流水序號</th>
                                <th>批次</th>
                                <th>張號</th>
                                <th>獎金</th>
                            </tr>
                        </thead>
                        <tbody>
                            {data.books.flatMap((b) =>
                                (b.prizes || []).map((v, i) => (
                                    <tr key={`${b.id}-${i}`}>
                                        <td className="ub-sticky ub__no">{b.serialNo || b.label}</td>
                                        <td>{b.batchKey}</td>
                                        <td>{i + 1}</td>
                                        <td className={v ? 'text-green' : ''}>
                                            {v ? `$${nf(v)}` : '—'}
                                        </td>
                                    </tr>
                                )),
                            )}
                        </tbody>
                    </table>
                </div>
            </>
        )
    }

    const netCurve = () => {
        if (!data.books.some((b) => b.prizes?.length)) return null
        const series = data.books
            .filter((b) => b.prizes?.length)
            .map((b) => cumulativeNet(b.prizes!, data.price))
        const all = series.flat()
        const lo = Math.min(0, ...all)
        const hi = Math.max(0, ...all)
        const W = 680
        const H = 170
        const x = (i: number) => 44 + (i / data.ticketsPerBook) * (W - 50)
        const y = (v: number) => 8 + (1 - (v - lo) / (hi - lo || 1)) * (H - 30)
        return (
            <>
                <h2 className="ub__section-title">累積淨損益曲線</h2>
                <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }} role="img">
                    <title>每本累積淨損益曲線</title>
                    <line x1={44} y1={y(0)} x2={W - 6} y2={y(0)} stroke="#e2e8f0" />
                    {[hi, 0, lo].map((v) => (
                        <text key={v} x={39} y={y(v) + 3.5} textAnchor="end" fontSize="9" fill="#64748b">
                            {v >= 0 ? '+' : ''}
                            {Math.round(v / 1000)}k
                        </text>
                    ))}
                    {series.map((pts, i) => (
                        <path
                            key={i}
                            d={`M${pts.map((v, j) => `${x(j + 1).toFixed(1)} ${y(v).toFixed(1)}`).join('L')}`}
                            fill="none"
                            stroke="#0b192c"
                            strokeWidth={1}
                            opacity={0.45}
                        />
                    ))}
                </svg>
                <p className="ub__note">
                    X 軸為刮到第幾張，Y 軸為「累計獎金 − 累計成本」。一條線代表一本。
                </p>
            </>
        )
    }

    const tabs = ['總覽', `每本明細 (${m.bookCount})`, '熱力圖', '原始資料']

    return (
        <div className="ub container">
            <SeoHead
                title={`${data.name || gameId} 整本開箱實測數據 — 大樣本統計`}
                description={`${data.name || gameId}（NO. ${gameId}）實測 ${m.bookCount} 本、${m.ticketCount} 張：實測回本率 ${pc(m.returnRate)}、中獎率 ${pc(m.winRate)}，逐本獎項分佈與官方獎金結構對照。`}
                path={`/unboxing/${gameId}`}
            />

            <Link to="/unboxing" className="ub__no" style={{ marginBottom: '0.6rem' }}>
                <ArrowLeft size={12} /> 回大樣本統計
            </Link>

            <div className="ub__detail-head">
                <div className="ub__detail-title">
                    <div className="ub__no">NO. {gameId}</div>
                    <h1>{data.name || gameId}</h1>
                    <div className="ub__meta">
                        ${data.price} / 張 ・ {data.ticketsPerBook} 張 / 本
                        {data.totalIssued > 0 && ` ・ 發行 ${nf(data.totalIssued)} 張`}
                        {data.issueDate && ` ・ 上市 ${data.issueDate}`}
                        {data.scratchcardId && (
                            <>
                                {' ・ '}
                                <Link to={`/detail/${data.scratchcardId}`}>看款式詳情與計算機</Link>
                            </>
                        )}
                    </div>
                </div>
                {session?.videoId ? (
                    <a
                        className="ub__video"
                        href={session.videoUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        <div className="ub__video-thumb">
                            <img
                                src={`https://i.ytimg.com/vi/${session.videoId}/maxresdefault.jpg`}
                                alt={session.videoTitle || session.title}
                                loading="lazy"
                                onError={(e) => {
                                    const img = e.currentTarget
                                    if (img.src.includes('maxresdefault')) {
                                        img.src = `https://i.ytimg.com/vi/${session.videoId}/hqdefault.jpg`
                                    }
                                }}
                            />
                        </div>
                        <div className="ub__video-cap">{session.videoTitle || session.title}</div>
                    </a>
                ) : (
                    <div className="ub__video">
                        <div className="ub__video-thumb">
                            <Play size={26} />
                        </div>
                        <div className="ub__video-cap">影片尚未上架，數據先行公開</div>
                    </div>
                )}
            </div>

            <div className="ub__kpi">
                {[
                    ['實測本數', `${m.bookCount} 本`],
                    ['實測張數', nf(m.ticketCount)],
                    ['總投入', `$${nf(m.cost)}`],
                    ['總回收', `$${nf(m.totalPrize)}`],
                    ['實測回本率', pc(m.returnRate)],
                    ['官方派彩率', pc(data.official.returnRate)],
                    ['實測中獎率', pc(m.winRate)],
                    ['官方中獎率', pc(data.official.winRate, 2)],
                ].map(([label, value], i) => (
                    <div className="ub__kpi-cell" key={label}>
                        <span>{label}</span>
                        <strong className={i === 4 ? 'ub-accent' : ''}>{value}</strong>
                    </div>
                ))}
            </div>

            <div className="ub__tabs">
                {tabs.map((t, i) => (
                    <button
                        key={t}
                        className={i === tab ? 'is-active' : ''}
                        onClick={() => setTab(i)}
                    >
                        {t}
                        {i === 3 && data.accessLevel < 2 ? ' 🔒' : ''}
                        {i === 1 && data.accessLevel < 1 ? ' 🔒' : ''}
                    </button>
                ))}
            </div>

            {tab === 0 && (
                <>
                    {overview()}
                    {netCurve()}
                </>
            )}
            {tab === 1 && gate(1, bookTable(sorted))}
            {tab === 2 && heatmap()}
            {tab === 3 && gate(2, raw())}

            <p className="ub__disclaimer">
                <strong>資料說明</strong>：本頁為刮刮研究室實際購買並逐張刮開的紀錄，
                共 {m.bookCount} 本、{nf(m.ticketCount)} 張。「官方派彩率」由台彩公布的獎金結構換算。
                實測樣本不等於母體，每張刮刮樂彼此獨立，<strong>過往數據無法預測未來</strong>；
                任何位置、序號、批次的規律都應視為隨機波動。本站資料僅供娛樂與研究，不構成投注建議。
            </p>
        </div>
    )
}
