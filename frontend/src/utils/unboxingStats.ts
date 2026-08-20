/**
 * 大樣本統計：純計算函式
 *
 * 全部無 React 依賴，方便單獨測試與在頁面間重用。
 * 注意：低權限使用者拿不到逐張 prizes 陣列，凡是吃 prizes 的函式都要先判斷有無資料。
 */

/** 最長連續未中獎張數 */
export function maxDryRun(prizes: number[]): number {
    let best = 0
    let cur = 0
    for (const p of prizes) {
        cur = p ? 0 : cur + 1
        if (cur > best) best = cur
    }
    return best
}

/** 累積淨損益（累計獎金 − 累計成本），長度同 prizes */
export function cumulativeNet(prizes: number[], price: number): number[] {
    let acc = 0
    return prizes.map((p) => {
        acc += p - price
        return acc
    })
}

/** 平均值 */
export function mean(xs: number[]): number {
    return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0
}

/** 母體標準差 */
export function stdDev(xs: number[]): number {
    if (!xs.length) return 0
    const m = mean(xs)
    return Math.sqrt(xs.reduce((a, b) => a + (b - m) * (b - m), 0) / xs.length)
}

/** 中位數 */
export function median(xs: number[]): number {
    if (!xs.length) return 0
    const s = [...xs].sort((a, b) => a - b)
    const mid = Math.floor(s.length / 2)
    return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2
}

/** 某值落在樣本中的百分位（0~1），用於「我的一本對照」 */
export function percentileOf(xs: number[], value: number): number {
    if (!xs.length) return 0
    const below = xs.filter((x) => x < value).length
    const equal = xs.filter((x) => x === value).length
    return (below + equal / 2) / xs.length
}

/** 把數列分箱成直方圖 */
export function histogram(xs: number[], bins = 8): { from: number; to: number; count: number }[] {
    if (!xs.length) return []
    const lo = Math.min(...xs)
    const hi = Math.max(...xs)
    if (lo === hi) return [{ from: lo, to: hi, count: xs.length }]
    const width = (hi - lo) / bins
    const out = Array.from({ length: bins }, (_, i) => ({
        from: lo + i * width,
        to: lo + (i + 1) * width,
        count: 0,
    }))
    for (const x of xs) {
        const idx = Math.min(bins - 1, Math.floor((x - lo) / width))
        out[idx].count++
    }
    return out
}

/**
 * 買 N 張模擬器：從實測資料放回抽樣 N 張，重複 trials 次
 *
 * 注意這是 bootstrap（有放回），回答的是「以這批實測的獎項分佈，隨機買 N 張會怎樣」，
 * 不是預測未來——每張刮刮樂彼此獨立，過往資料無法預測後續開獎。
 */
export function simulateDraws(
    pool: number[],
    n: number,
    price: number,
    trials = 5000,
): { breakEvenRate: number; nets: number[]; medianNet: number; best: number; worst: number } {
    if (!pool.length || n <= 0) {
        return { breakEvenRate: 0, nets: [], medianNet: 0, best: 0, worst: 0 }
    }
    const cost = n * price
    const nets: number[] = []
    let breakEven = 0
    for (let t = 0; t < trials; t++) {
        let sum = 0
        for (let i = 0; i < n; i++) {
            sum += pool[(Math.random() * pool.length) | 0]
        }
        const net = sum - cost
        nets.push(net)
        if (net >= 0) breakEven++
    }
    return {
        breakEvenRate: breakEven / trials,
        nets,
        medianNet: median(nets),
        best: Math.max(...nets),
        worst: Math.min(...nets),
    }
}

/**
 * 各張號中獎次數是否偏離隨機
 *
 * 以整體中獎率 p 與本數 n 算二項分布的 95% 區間，回報有幾個張號落在區間外。
 * 期望值本來就會有約 5% 的張號落在區間外，這點要在畫面上講清楚，
 * 否則反而會製造「有規律」的錯覺。
 */
export function positionOutliers(
    positionWins: number[],
    bookCount: number,
    overallWinRate: number,
): { low: number; high: number; outliers: number; expectedOutliers: number } {
    if (!bookCount || !positionWins.length) {
        return { low: 0, high: 0, outliers: 0, expectedOutliers: 0 }
    }
    const p = overallWinRate
    const sd = Math.sqrt(bookCount * p * (1 - p))
    const centre = bookCount * p
    const low = Math.max(0, centre - 1.96 * sd)
    const high = centre + 1.96 * sd
    const outliers = positionWins.filter((w) => w < low || w > high).length
    return { low, high, outliers, expectedOutliers: positionWins.length * 0.05 }
}

/** 前 / 中 / 後三段的回收金額 */
export function thirds(prizesByBook: number[][]): [number, number, number] {
    const out: [number, number, number] = [0, 0, 0]
    for (const prizes of prizesByBook) {
        const size = prizes.length / 3
        prizes.forEach((v, i) => {
            out[Math.min(2, Math.floor(i / size))] += v
        })
    }
    return out
}
