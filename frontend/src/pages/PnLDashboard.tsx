/**
 * 「我的錢包」個人損益儀表板
 * 改為後端 API 持久化 (LINE 登入後跨裝置同步)
 * 含累計損益折線圖、投報率圓環指標
 * 支援:
 * - 中獎紀錄選填縣市 + opt-in 同步到全台熱區 (匿名)
 * - 縣市偏好寫入 user.lastCheckinCity (下次預設帶入)
 */
import { useState, useEffect, useCallback } from 'react'
import { motion } from 'framer-motion'
import { Plus, Trash2, Wallet, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react'
import { Autocomplete, TextField, CircularProgress, Checkbox, FormControlLabel, MenuItem } from '@mui/material'
import {
    ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
    CartesianGrid, Tooltip, PieChart, Pie, Cell
} from 'recharts'
import SeoHead from '../components/SeoHead'
import {
    searchScratchcardsPublic,
    fetchWalletRecords, createWalletRecord, deleteWalletRecord,
    fetchWalletPreferences, updateWalletPreferences,
    type ScratchcardSearchItem as ScratchcardOption,
    type PnLRecordRow,
} from '../hooks/api'
import { TAIWAN_CITIES } from '../constants/cities'
import { useUser } from '../hooks/useUser'
import './PnLDashboard.css'

/** 兼容 chart 元件用的精簡型 (id 為字串以符合既有 chart 邏輯) */
interface PnLRecord {
    id: string
    date: string
    gameName: string
    spent: number
    won: number
}

/** 把後端 row 轉為 chart 用的 PnLRecord */
function toChartRecord(r: PnLRecordRow): PnLRecord {
    return {
        id: String(r.id),
        date: r.createdAt ? new Date(r.createdAt).toLocaleDateString('zh-TW') : '',
        gameName: r.gameName || '未指定',
        spent: r.spent,
        won: r.won,
    }
}

/** 一次性遷移: 把舊 localStorage 紀錄上傳到後端後刪掉 */
const LEGACY_STORAGE_KEY = 'scratchcard_pnl'
const MIGRATED_FLAG = 'scratchcard_pnl_migrated'

/**
 * 累計 PnL 折線圖 — 使用 Recharts
 */
function PnLLineChart({ records }: { records: PnLRecord[] }) {
    if (records.length < 2) return (
        <div className="pnl__chart glass-card pnl__chart--empty">
            <p>需至少 2 筆紀錄才可顯示走勢圖</p>
        </div>
    )

    // 計算累計損益序列（從舊到新）
    const reversed = [...records].reverse()
    let cumulative = 0
    const data = reversed.map((r, i) => {
        cumulative += (r.won - r.spent)
        return {
            index: i + 1,
            game: r.gameName,
            pnl: cumulative,
            date: r.date
        }
    })

    const lastPnl = data[data.length - 1].pnl
    const isProfit = lastPnl >= 0
    const mainColor = isProfit ? '#1E8449' : '#D32F2F'

    return (
        <div className="pnl__chart glass-card">
            <h2>
                <BarChart3 size={16} />
                損益累積趨勢
            </h2>
            <div style={{ width: '100%', height: 160 }}>
                <ResponsiveContainer>
                    <AreaChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                        <defs>
                            <linearGradient id="colorPnl" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={mainColor} stopOpacity={0.3} />
                                <stop offset="95%" stopColor={mainColor} stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                        <XAxis dataKey="index" hide />
                        <YAxis 
                            orientation="right" 
                            fontSize={10} 
                            tickFormatter={(val) => `$${val}`}
                            stroke="rgba(255,255,255,0.3)"
                        />
                        <Tooltip
                            contentStyle={{ 
                                backgroundColor: 'rgba(11, 25, 44, 0.95)', 
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: '8px',
                                fontSize: '12px'
                            }}
                            itemStyle={{ color: '#fff' }}
                            formatter={(value: any) => [`$${Number(value).toLocaleString()}`, '累計損益']}
                            labelFormatter={(label) => `第 ${label} 筆`}
                        />
                        <Area
                            type="monotone"
                            dataKey="pnl"
                            stroke={mainColor}
                            strokeWidth={3}
                            fillOpacity={1}
                            fill="url(#colorPnl)"
                            animationDuration={1500}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
            <div className="pnl__chart-footer">
                <span style={{ color: mainColor, fontWeight: 700 }}>
                    目前：{isProfit ? '+' : ''}{lastPnl.toLocaleString()}
                </span>
            </div>
        </div>
    )
}

/**
 * 投報率圓環指標 — 使用 Recharts PieChart
 */
function ROIGauge({ spent, won }: { spent: number; won: number }) {
    if (spent === 0) return null

    const roi = Math.round((won / spent) * 100)
    const isProfit = roi >= 100
    const mainColor = isProfit ? '#1E8449' : '#D32F2F'
    
    // PieChart 資料：進度與剩餘
    const data = [
        { name: 'ROI', value: Math.min(roi, 100) },
        { name: 'Remaining', value: Math.max(0, 100 - roi) }
    ]

    return (
        <div className="pnl__gauge glass-card">
            <div style={{ position: 'relative', width: 120, height: 120 }}>
                <ResponsiveContainer>
                    <PieChart>
                        <Pie
                            data={data}
                            innerRadius={42}
                            outerRadius={50}
                            paddingAngle={0}
                            dataKey="value"
                            startAngle={90}
                            endAngle={-270}
                            stroke="none"
                        >
                            <Cell fill={mainColor} />
                            <Cell fill="rgba(255,255,255,0.05)" />
                        </Pie>
                    </PieChart>
                </ResponsiveContainer>
                <div className="pnl__gauge-center">
                    <span className="pnl__gauge-value" style={{ color: mainColor }}>{roi}%</span>
                    <span className="pnl__gauge-label">投報率</span>
                </div>
            </div>
        </div>
    )
}

export default function PnLDashboard() {
    const { user } = useUser()
    const [rawRecords, setRawRecords] = useState<PnLRecordRow[]>([])
    const records: PnLRecord[] = rawRecords.map(toChartRecord)
    const [selectedGame, setSelectedGame] = useState<ScratchcardOption | null>(null)
    const [inputValue, setInputValue] = useState('')
    const [options, setOptions] = useState<ScratchcardOption[]>([])
    const [loading, setLoading] = useState(false)

    const [spent, setSpent] = useState('')
    const [won, setWon] = useState('')
    const [city, setCity] = useState('')
    const [shareToHeatmap, setShareToHeatmap] = useState(false)

    /** 載入紀錄 + 偏好 + 一次性 localStorage 遷移 */
    const reload = useCallback(async () => {
        if (!user) return
        try {
            const [rows, prefs] = await Promise.all([
                fetchWalletRecords(),
                fetchWalletPreferences(),
            ])
            setRawRecords(rows)
            if (prefs.lastCheckinCity) setCity(prefs.lastCheckinCity)
            // 一次性遷移舊 localStorage
            if (!localStorage.getItem(MIGRATED_FLAG)) {
                try {
                    const raw = localStorage.getItem(LEGACY_STORAGE_KEY)
                    const legacy: any[] = raw ? JSON.parse(raw) : []
                    if (Array.isArray(legacy) && legacy.length > 0 && rows.length === 0) {
                        if (window.confirm(`發現 ${legacy.length} 筆本機舊紀錄，要上傳到雲端讓多裝置同步嗎？`)) {
                            for (const r of legacy) {
                                await createWalletRecord({
                                    gameName: r.gameName || '',
                                    spent: Number(r.spent) || 0,
                                    won: Number(r.won) || 0,
                                })
                            }
                            const fresh = await fetchWalletRecords()
                            setRawRecords(fresh)
                        }
                    }
                    localStorage.setItem(MIGRATED_FLAG, '1')
                    localStorage.removeItem(LEGACY_STORAGE_KEY)
                } catch { /* ignore */ }
            }
        } catch {
            setRawRecords([])
        }
    }, [user])

    useEffect(() => { reload() }, [reload])

    // Debounce search
    useEffect(() => {
        if (!inputValue) {
            setOptions([])
            return
        }
        const timer = setTimeout(async () => {
            setLoading(true)
            try {
                const res = await searchScratchcardsPublic(inputValue)
                setOptions(res)
            } catch {
                setOptions([])
            } finally {
                setLoading(false)
            }
        }, 300)
        return () => clearTimeout(timer)
    }, [inputValue])

    /** 統計數據 */
    const totalSpent = records.reduce((s: number, r: PnLRecord) => s + r.spent, 0)
    const totalWon = records.reduce((s: number, r: PnLRecord) => s + r.won, 0)
    const totalPnL = totalWon - totalSpent

    async function handleAdd() {
        if (!spent) return
        try {
            await createWalletRecord({
                gameName: selectedGame ? selectedGame.name : (inputValue || '未指定'),
                scratchcardId: selectedGame?.id ?? null,
                spent: Number(spent),
                won: Number(won) || 0,
                city: city || null,
                sharedToPublic: shareToHeatmap && !!city && Number(won) > 0,
            })
            // 同步用戶縣市偏好
            if (city) {
                try { await updateWalletPreferences({ lastCheckinCity: city }) } catch {/*ignore*/}
            }
            setSelectedGame(null)
            setInputValue('')
            setSpent('')
            setWon('')
            // 縣市保留作為下次預設, shareToHeatmap 不重置 (使用者偏好黏性)
            await reload()
        } catch (e) {
            alert('新增失敗，請確認已登入。')
        }
    }

    async function handleDelete(id: string) {
        try {
            await deleteWalletRecord(Number(id))
            await reload()
        } catch {
            alert('刪除失敗')
        }
    }

    return (
        <div className="pnl container">
            <SeoHead
                title="我的錢包 — 刮刮樂損益儀表板"
                description="記錄你的刮刮樂花費與中獎金額，自動計算累計損益、投報率與走勢圖。"
                path="/wallet"
            />
            <motion.h1
                className="pnl__title"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
            >
                💰 我的錢包
            </motion.h1>

            {/* 總覽卡片 */}
            <div className="pnl__summary">
                <div className="pnl__stat glass-card">
                    <TrendingDown size={20} className="pnl__stat-icon pnl__stat-icon--spent" />
                    <span>總花費</span>
                    <strong>${totalSpent.toLocaleString()}</strong>
                </div>
                <div className="pnl__stat glass-card">
                    <TrendingUp size={20} className="pnl__stat-icon pnl__stat-icon--won" />
                    <span>總中獎</span>
                    <strong>${totalWon.toLocaleString()}</strong>
                </div>
                <div className={`pnl__stat glass-card ${totalPnL >= 0 ? 'pnl__stat--profit' : 'pnl__stat--loss'}`}>
                    <Wallet size={20} className="pnl__stat-icon" />
                    <span>盈虧</span>
                    <strong>{totalPnL >= 0 ? '+' : ''}${totalPnL.toLocaleString()}</strong>
                </div>
            </div>

            {/* 圖表區 — 折線圖 + 圓環指標 */}
            {records.length > 0 && (
                <motion.div
                    className="pnl__charts"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                >
                    <PnLLineChart records={records} />
                    <ROIGauge spent={totalSpent} won={totalWon} />
                </motion.div>
            )}

            {/* 新增紀錄 */}
            <div className="pnl__form glass-card">
                <h2>新增紀錄</h2>
                <div className="pnl__form-row">
                    <Autocomplete
                        freeSolo
                        options={options}
                        getOptionLabel={(option) => typeof option === 'string' ? option : `${option.gameId} ${option.name}`}
                        value={selectedGame}
                        onChange={(_: any, newValue: any) => {
                            if (typeof newValue === 'string') {
                                setSelectedGame(null)
                                setInputValue(newValue)
                            } else {
                                setSelectedGame(newValue)
                            }
                        }}
                        inputValue={inputValue}
                        onInputChange={(_: any, newInputValue: string) => setInputValue(newInputValue)}
                        loading={loading}
                        renderInput={(params: any) => (
                            <TextField
                                {...params}
                                placeholder="款式名稱（可搜尋）"
                                variant="outlined"
                                size="small"
                                InputProps={{
                                    ...params.InputProps,
                                    endAdornment: (
                                        <>
                                            {loading ? <CircularProgress color="inherit" size={20} /> : null}
                                            {params.InputProps.endAdornment}
                                        </>
                                    ),
                                }}
                                sx={{
                                    bgcolor: 'rgba(255, 255, 255, 0.05)',
                                    borderRadius: '8px',
                                    input: { color: 'var(--color-text-primary)' },
                                    fieldset: { borderColor: 'var(--color-border)', borderRadius: '8px' },
                                    '& .MuiOutlinedInput-root': {
                                        padding: '4px 39px 4px 8px !important',
                                        '&:hover fieldset': { borderColor: 'var(--color-primary)' },
                                        '&.Mui-focused fieldset': { borderColor: 'var(--color-primary)' }
                                    }
                                }}
                            />
                        )}
                        sx={{ flex: 1, minWidth: '180px', '& .MuiAutocomplete-inputRoot': { padding: '4px' } }}
                    />
                    <input type="number" placeholder="花費金額" value={spent} onChange={(e) => setSpent(e.target.value)} />
                    <input type="number" placeholder="中獎金額" value={won} onChange={(e) => setWon(e.target.value)} />
                    <button className="pnl__add-btn" onClick={handleAdd}>
                        <Plus size={16} /> 新增
                    </button>
                </div>

                {/* 第二排: 縣市選擇 + 分享到熱區 (中獎才顯示) */}
                {Number(won) > 0 && (
                    <div className="pnl__form" style={{ marginTop: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                        <TextField
                            select
                            label="中獎縣市（選填）"
                            value={city}
                            onChange={(e) => setCity(e.target.value)}
                            size="small"
                            sx={{
                                minWidth: 160,
                                bgcolor: 'rgba(255,255,255,0.05)', borderRadius: '8px',
                                '& .MuiInputLabel-root': { color: 'var(--color-text-secondary)' },
                                '& .MuiSelect-select': { color: 'var(--color-text-primary)' },
                                '& fieldset': { borderColor: 'var(--color-border)' },
                            }}
                        >
                            <MenuItem value=""><em>不指定</em></MenuItem>
                            {TAIWAN_CITIES.map(c => (
                                <MenuItem key={c} value={c}>{c}</MenuItem>
                            ))}
                        </TextField>
                        <FormControlLabel
                            control={
                                <Checkbox
                                    checked={shareToHeatmap}
                                    onChange={(e) => setShareToHeatmap(e.target.checked)}
                                    disabled={!city}
                                    sx={{ color: 'var(--color-text-secondary)' }}
                                />
                            }
                            label={
                                <span style={{ fontSize: 14, color: 'var(--color-text-primary)' }}>
                                    📢 同步到全台熱區（匿名公開，不含個人資訊）
                                </span>
                            }
                        />
                    </div>
                )}

                {!user && (
                    <p style={{ marginTop: 12, fontSize: 13, color: 'var(--color-text-secondary)' }}>
                        ⚠️ 尚未登入，紀錄無法雲端同步。請先用右上角「LINE 登入」登入後再記帳。
                    </p>
                )}
            </div>

            {/* 紀錄列表 */}
            {records.length > 0 && (
                <div className="pnl__list glass-card">
                    <h2>歷史紀錄</h2>
                    {records.map((r: PnLRecord) => (
                        <div key={r.id} className="pnl__record">
                            <div className="pnl__record-info">
                                <span className="pnl__record-name">{r.gameName}</span>
                                <span className="pnl__record-date">{r.date}</span>
                            </div>
                            {/* 小型比例條 */}
                            <div className="pnl__record-bar-wrap">
                                <div
                                    className="pnl__record-bar pnl__record-bar--spent"
                                    style={{ width: `${Math.min(100, (r.spent / Math.max(r.spent, r.won, 1)) * 100)}%` }}
                                />
                                <div
                                    className="pnl__record-bar pnl__record-bar--won"
                                    style={{ width: `${Math.min(100, (r.won / Math.max(r.spent, r.won, 1)) * 100)}%` }}
                                />
                            </div>
                            <div className="pnl__record-numbers">
                                <span className="pnl__record-spent">-${r.spent}</span>
                                <span className="pnl__record-won">+${r.won}</span>
                                <span className={r.won - r.spent >= 0 ? 'text-green' : 'text-red'}>
                                    {r.won - r.spent >= 0 ? '+' : ''}${r.won - r.spent}
                                </span>
                            </div>
                            <button className="pnl__delete" onClick={() => handleDelete(r.id)}>
                                <Trash2 size={14} />
                            </button>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
