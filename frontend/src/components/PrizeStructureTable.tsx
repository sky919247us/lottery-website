/**
 * 獎金結構表（可重用）
 *
 * 原本寫死在 pages/Detail.tsx，抽出來給「大樣本統計」分頁共用。
 * 樣式沿用 Detail.css 的 .detail__table* 類別（全域 import，可跨頁使用）。
 */
import type { PrizeStructure } from '../hooks/api'

interface Props {
    prizes: PrizeStructure[]
    /** 銷售率數值（0~100），用來估算剩餘張數 */
    salesRateValue?: number
    /** 預告款尚未公佈完整結構時，空狀態文案不同 */
    isPreview?: boolean
    /** 顯示「理論每本期望張數」欄，需搭配 totalIssued 與 ticketsPerBook */
    showPerBook?: boolean
    totalIssued?: number
    ticketsPerBook?: number
    /** 顯示「實測平均張數」欄：獎金金額 → 實測總張數 */
    measuredCounts?: Record<string, number>
    /** 實測本數，用來把 measuredCounts 換算成每本平均 */
    measuredBookCount?: number
    /** 是否顯示「剩餘」欄（大樣本統計頁不需要） */
    showRemaining?: boolean
}

export default function PrizeStructureTable({
    prizes,
    salesRateValue = 0,
    isPreview = false,
    showPerBook = false,
    totalIssued = 0,
    ticketsPerBook = 0,
    measuredCounts,
    measuredBookCount = 0,
    showRemaining = true,
}: Props) {
    if (!prizes.length) {
        return (
            <p className="detail__empty">
                {isPreview
                    ? '預告款尚未公佈完整獎金結構，正式發售後將自動更新'
                    : '暫無獎金結構資料'}
            </p>
        )
    }

    const canPerBook = showPerBook && totalIssued > 0 && ticketsPerBook > 0
    const showMeasured = !!measuredCounts && measuredBookCount > 0

    return (
        <div className="detail__table-wrap">
            <table className="detail__table">
                <thead>
                    <tr>
                        <th>獎項</th>
                        <th>總數</th>
                        {showRemaining && <th>剩餘</th>}
                        {canPerBook && <th>理論每本</th>}
                        {showMeasured && <th>實測每本</th>}
                        {canPerBook && showMeasured && <th>差異</th>}
                    </tr>
                </thead>
                <tbody>
                    {prizes.map((p, i) => {
                        // 估算剩餘：依銷售率估算已開出比例
                        const salesRatio = salesRateValue / 100
                        const estimatedRemaining = Math.round(p.totalCount * (1 - salesRatio))
                        const expected = canPerBook
                            ? (p.totalCount / totalIssued) * ticketsPerBook
                            : 0
                        const measured = showMeasured
                            ? (measuredCounts![String(p.prizeAmount)] || 0) / measuredBookCount
                            : 0
                        const diff = measured - expected
                        const seen = measured > 0 || expected >= 0.5
                        return (
                            <tr key={i}>
                                <td className="detail__amount">
                                    {p.prizeAmount > 0
                                        ? `$${p.prizeAmount.toLocaleString()}`
                                        : p.prizeName}
                                </td>
                                <td>{p.totalCount.toLocaleString()}</td>
                                {showRemaining && (
                                    <td className="detail__remaining-count-cell">
                                        {estimatedRemaining.toLocaleString()}
                                    </td>
                                )}
                                {canPerBook && <td>{expected.toFixed(2)}</td>}
                                {showMeasured && <td>{seen ? measured.toFixed(2) : '·'}</td>}
                                {canPerBook && showMeasured && (
                                    <td className={diff >= 0 ? 'text-green' : 'text-red'}>
                                        {seen ? `${diff >= 0 ? '+' : ''}${diff.toFixed(2)}` : '—'}
                                    </td>
                                )}
                            </tr>
                        )
                    })}
                </tbody>
            </table>
            {showRemaining && (
                <p className="detail__table-note">* 剩餘數量為依銷售率估算，僅供參考</p>
            )}
        </div>
    )
}
