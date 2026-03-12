/**
 * 「我的錢包」個人損益儀表板
 * 使用 LocalStorage 儲存損益紀錄
 * 含累計損益折線圖（SVG）與投報率圓環指標
 */
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Plus, Trash2, Wallet, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react'
import { Autocomplete, TextField, CircularProgress } from '@mui/material'
import SeoHead from '../components/SeoHead'
import { searchScratchcardsPublic, type ScratchcardSearchItem as ScratchcardOption } from '../hooks/api'
import './PnLDashboard.css'

interface PnLRecord {
    id: string
    date: string
    gameName: string
    spent: number
    won: number
}

const STORAGE_KEY = 'scratchcard_pnl'

function loadRecords(): PnLRecord[] {
    try {
        const raw = localStorage.getItem(STORAGE_KEY)
        return raw ? JSON.parse(raw) : []
    } catch {
        return []
    }
}

function saveRecords(records: PnLRecord[]) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(records))
}

/**
 * 累計 PnL 折線圖 — 純 SVG
 * 將每筆紀錄的累計損益繪製為帶漸層填充的折線
 */
function PnLLineChart({ records }: { records: PnLRecord[] }) {
    if (records.length < 2) return null

    const width = 400
    const height = 140
    const paddingX = 32
    const paddingY = 20

    // 計算累計損益序列（從舊到新）
    const reversed = [...records].reverse()
    const cumPnl: number[] = []
    reversed.reduce((acc, r) => {
        const next = acc + (r.won - r.spent)
        cumPnl.push(next)
        return next
    }, 0)

    const maxVal = Math.max(...cumPnl, 0)
    const minVal = Math.min(...cumPnl, 0)
    const range = maxVal - minVal || 1

    const chartW = width - paddingX * 2
    const chartH = height - paddingY * 2

    const points = cumPnl.map((val, i) => {
        const x = paddingX + (i / (cumPnl.length - 1)) * chartW
        const y = paddingY + (1 - (val - minVal) / range) * chartH
        return { x, y, val }
    })

    const polyline = points.map(p => `${p.x},${p.y}`).join(' ')

    // 填充區域路徑
    const lastPnl = cumPnl[cumPnl.length - 1]
    const isProfit = lastPnl >= 0
    const fillColor = isProfit ? '#1E8449' : '#D32F2F'
    const areaPath = `M${points[0].x},${height - paddingY} ${points.map(p => `L${p.x},${p.y}`).join(' ')} L${points[points.length - 1].x},${height - paddingY} Z`

    // 零線 Y 座標
    const zeroY = paddingY + (1 - (0 - minVal) / range) * chartH

    return (
        <div className="pnl__chart glass-card">
            <h2>
                <BarChart3 size={16} />
                累計損益走勢
            </h2>
            <svg
                className="pnl__line-svg"
                viewBox={`0 0 ${width} ${height}`}
                preserveAspectRatio="none"
            >
                <defs>
                    {/* 漸層填充 */}
                    <linearGradient id="pnl-fill" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor={fillColor} stopOpacity="0.25" />
                        <stop offset="100%" stopColor={fillColor} stopOpacity="0.02" />
                    </linearGradient>
                </defs>

                {/* 零線 */}
                {minVal < 0 && maxVal > 0 && (
                    <line
                        x1={paddingX} y1={zeroY}
                        x2={width - paddingX} y2={zeroY}
                        stroke="var(--color-border)" strokeWidth="1"
                        strokeDasharray="4,4"
                    />
                )}

                {/* 填充區域 */}
                <path d={areaPath} fill="url(#pnl-fill)" className="pnl__area-path" />

                {/* 折線 */}
                <polyline
                    points={polyline}
                    fill="none"
                    stroke={fillColor}
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="pnl__polyline"
                />

                {/* 最後一個點 — 圓點 */}
                <circle
                    cx={points[points.length - 1].x}
                    cy={points[points.length - 1].y}
                    r="4"
                    fill={fillColor}
                    stroke="#FFFFFF"
                    strokeWidth="2"
                />

                {/* 最後數值標註 */}
                <text
                    x={points[points.length - 1].x}
                    y={points[points.length - 1].y - 10}
                    textAnchor="end"
                    fill={fillColor}
                    fontSize="11"
                    fontWeight="700"
                    fontFamily="var(--font-display)"
                >
                    {lastPnl >= 0 ? '+' : ''}{lastPnl.toLocaleString()}
                </text>
            </svg>
        </div>
    )
}

/**
 * 投報率圓環指標 — SVG circle + stroke-dasharray
 */
function ROIGauge({ spent, won }: { spent: number; won: number }) {
    if (spent === 0) return null

    const roi = Math.round((won / spent) * 100)
    const displayRoi = Math.min(roi, 200) // 上限 200% 避免溢出
    const radius = 48
    const circumference = 2 * Math.PI * radius
    const progress = Math.min(displayRoi / 200, 1) // 200% = 滿圓
    const dashOffset = circumference * (1 - progress)
    const isProfit = roi >= 100

    return (
        <div className="pnl__gauge glass-card">
            <svg className="pnl__gauge-svg" viewBox="0 0 120 120">
                {/* 背景圓環 */}
                <circle
                    cx="60" cy="60" r={radius}
                    fill="none"
                    stroke="var(--color-separator)"
                    strokeWidth="8"
                />
                {/* 進度圓環 */}
                <circle
                    cx="60" cy="60" r={radius}
                    fill="none"
                    stroke={isProfit ? '#1E8449' : '#D32F2F'}
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={dashOffset}
                    transform="rotate(-90 60 60)"
                    className="pnl__gauge-circle"
                />
                {/* 中心數值 */}
                <text
                    x="60" y="56"
                    textAnchor="middle"
                    fill={isProfit ? '#1E8449' : '#D32F2F'}
                    fontSize="22"
                    fontWeight="800"
                    fontFamily="var(--font-display)"
                >
                    {roi}%
                </text>
                <text
                    x="60" y="72"
                    textAnchor="middle"
                    fill="var(--color-text-tertiary)"
                    fontSize="9"
                    fontWeight="500"
                >
                    投報率
                </text>
            </svg>
        </div>
    )
}

export default function PnLDashboard() {
    const [records, setRecords] = useState<PnLRecord[]>(loadRecords)
    const [selectedGame, setSelectedGame] = useState<ScratchcardOption | null>(null)
    const [inputValue, setInputValue] = useState('')
    const [options, setOptions] = useState<ScratchcardOption[]>([])
    const [loading, setLoading] = useState(false)

    const [spent, setSpent] = useState('')
    const [won, setWon] = useState('')

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

    useEffect(() => {
        saveRecords(records)
    }, [records])

    /** 統計數據 */
    const totalSpent = records.reduce((s, r) => s + r.spent, 0)
    const totalWon = records.reduce((s, r) => s + r.won, 0)
    const totalPnL = totalWon - totalSpent

    function handleAdd() {
        if (!spent) return
        const newRecord: PnLRecord = {
            id: Date.now().toString(),
            date: new Date().toLocaleDateString('zh-TW'),
            gameName: selectedGame ? selectedGame.name : (inputValue || '未指定'),
            spent: Number(spent),
            won: Number(won) || 0,
        }
        setRecords([newRecord, ...records])
        setSelectedGame(null)
        setInputValue('')
        setSpent('')
        setWon('')
    }

    function handleDelete(id: string) {
        setRecords(records.filter((r) => r.id !== id))
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
                        onChange={(_, newValue) => {
                            if (typeof newValue === 'string') {
                                setSelectedGame(null)
                                setInputValue(newValue)
                            } else {
                                setSelectedGame(newValue)
                            }
                        }}
                        inputValue={inputValue}
                        onInputChange={(_, newInputValue) => setInputValue(newInputValue)}
                        loading={loading}
                        renderInput={(params) => (
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
            </div>

            {/* 紀錄列表 */}
            {records.length > 0 && (
                <div className="pnl__list glass-card">
                    <h2>歷史紀錄</h2>
                    {records.map((r) => (
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
