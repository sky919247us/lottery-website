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

/** 標準常態累積分布（Abramowitz & Stegun 7.1.26 的 erf 近似） */
function normalCdf(z: number): number {
    const sign = z < 0 ? -1 : 1
    const x = Math.abs(z) / Math.SQRT2
    const t = 1 / (1 + 0.3275911 * x)
    const y =
        1 -
        ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t +
            0.254829592) *
            t *
            Math.exp(-x * x)
    return 0.5 * (1 + sign * y)
}

/**
 * 張號位置的卡方適合度檢定
 *
 * 檢定「各張號的中獎次數是否符合均勻分布」。這比「數有幾個張號落在 95% 區間外」
 * 正確：後者在本數不多時常態近似很粗糙，又沒處理多重比較，100 個張號本來就會有
 * 約 5 個純屬巧合地落在區間外，很容易被誤讀成有規律。
 *
 * p 值用 Wilson–Hilferty 轉換近似，df 大時足夠準確。
 */
export function chiSquareUniform(counts: number[]): {
    chi2: number
    df: number
    p: number
    significant: boolean
} {
    const n = counts.length
    const total = counts.reduce((a, b) => a + b, 0)
    const expected = n ? total / n : 0
    if (!expected || n < 2) return { chi2: 0, df: 0, p: 1, significant: false }
    const chi2 = counts.reduce((a, c) => a + ((c - expected) * (c - expected)) / expected, 0)
    const df = n - 1
    const z =
        (Math.cbrt(chi2 / df) - (1 - 2 / (9 * df))) / Math.sqrt(2 / (9 * df))
    const p = 1 - normalCdf(z)
    return { chi2, df, p, significant: p < 0.05 }
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
