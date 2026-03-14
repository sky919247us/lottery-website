/**
 * 「我的錢包」個人損益儀表板
 * 使用 LocalStorage 儲存損益紀錄
 * 含累計損益折線圖（SVG）與投報率圓環指標
 */
import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { Plus, Trash2, Wallet, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react'
import { Autocomplete, TextField, CircularProgress } from '@mui/material'
import {
    ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
    CartesianGrid, Tooltip, PieChart, Pie, Cell
} from 'recharts'
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
    const totalSpent = records.reduce((s: number, r: PnLRecord) => s + r.spent, 0)
    const totalWon = records.reduce((s: number, r: PnLRecord) => s + r.won, 0)
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
