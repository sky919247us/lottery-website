/**
 * 社群地圖頁面 — Phase 2/3/4 完整版
 *
 * 功能：
 * 1. 全台經銷商搜尋 + 篩選（縣市、來源、設施標籤）
 * 2. 經銷商列表 + 地圖連結 + 認證/專業版徽章
 * 3. 中獎打卡回報（沿用 Checkin API）
 * 4. 庫存回報（GPS 驗證 + 燈號）
 * 5. Karma 等級顯示
 * 6. 臨時公告顯示
 * 7. 節慶庫存快報（banner + 熱力圖）
 */
import { useEffect, useState, useMemo, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
    MapPin, Search, Send, Store, Navigation,
    Filter, X, ChevronDown, Flame, ExternalLink,
    Shield, Star, Megaphone, Package, PartyPopper, Map as MapIcon, List
} from 'lucide-react'
import { Link } from 'react-router-dom'
import {
    fetchRetailers, fetchCheckins, createCheckin,
    fetchInventory, reportInventory, fetchMerchantOfficialInventory,
    fetchFestivalStatus, fetchHeatmap, searchScratchcardsPublic,
    recordRetailerClick,
    type RetailerData, type CheckinData, type InventoryItem, type MerchantInventoryData,
    type FestivalStatus, type HeatmapPoint, type ScratchcardSearchItem
} from '../hooks/api'

import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import MarkerClusterGroup from 'react-leaflet-cluster'
import L from 'leaflet'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import 'leaflet.markercluster/dist/MarkerCluster.Default.css'
import HeatmapLayer from '../components/HeatmapLayer'
import RatingDisplay from '../components/RatingDisplay'
import RatingPanel from '../components/RatingPanel'
import SeoHead from '../components/SeoHead'

// 修正 Leaflet 預設 Icon 路徑問題
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

import { useUser } from '../hooks/useUser'
import './CommunityMap.css'

/** 22 縣市列表 */
const CITIES = [
    '台北市', '新北市', '桃園市', '台中市', '台南市', '高雄市',
    '基隆市', '新竹市', '新竹縣', '苗栗縣', '彰化縣', '南投縣',
    '雲林縣', '嘉義市', '嘉義縣', '屏東縣', '宜蘭縣', '花蓮縣',
    '台東縣', '澎湖縣', '金門縣', '連江縣',
]

/** 來源 */
const SOURCES = ['全部', '台灣彩券', '台灣運彩']

/** 設施標籤篩選設定 */
const TAG_FILTERS = [
    { key: 'hasAC', label: '❄️ 冷氣' },
    { key: 'hasSeats', label: '💺 座位' },
    { key: 'hasWifi', label: '📶 Wi-Fi' },
    { key: 'hasEPay', label: '💳 電子支付' },
    { key: 'hasStrategy', label: '📋 攻略' },
    { key: 'hasNumberPick', label: '🔢 挑號' },
    { key: 'hasScratchBoard', label: '🪣 刮板' },
    { key: 'hasSportTV', label: '📺 運彩轉播' },
    { key: 'hasReadingGlasses', label: '👓 老花眼鏡' },
]

/** 設施圖示對照表（Pop-up 與卡片內使用） */
const FACILITY_ICONS: Record<string, string> = {
    hasAC: '❄️', hasToilet: '🚻', hasSeats: '💺', hasWifi: '📶',
    hasAccessibility: '♿', hasEPay: '💳', hasStrategy: '📋',
    hasNumberPick: '🔢', hasScratchBoard: '🪣', hasMagnifier: '🔍',
    hasReadingGlasses: '👓', hasNewspaper: '📰', hasSportTV: '📺',
}
const FACILITY_LABELS: Record<string, string> = {
    hasAC: '冷氣', hasToilet: '廁所', hasSeats: '座位', hasWifi: 'Wi-Fi',
    hasAccessibility: '無障礙', hasEPay: '電子支付', hasStrategy: '攻略',
    hasNumberPick: '挑號', hasScratchBoard: '刮板', hasMagnifier: '放大鏡',
    hasReadingGlasses: '老花眼鏡', hasNewspaper: '報紙', hasSportTV: '運彩轉播',
}

/** 取得 Pro 店家的啟用設施列表 */
function getActiveFacilities(r: RetailerData): string[] {
    return Object.keys(FACILITY_ICONS).filter(k => (r as unknown as Record<string, boolean>)[k])
}

/** 庫存狀態選項（保留） */
const INVENTORY_STATUS = [
    { value: '充足', label: '🟢 充足', color: '#22c55e' },
    { value: '少量', label: '🟡 少量', color: '#eab308' },
    { value: '完售', label: '🔴 完售', color: '#ef4444' },
]

/** Karma 等級色彩 */
const LEVEL_COLORS = [
    '#94a3b8', '#6ee7b7', '#34d399', '#10b981',
    '#f59e0b', '#f97316', '#ef4444', '#dc2626',
    '#a855f7', '#d4af37',
]

/** 每頁顯示筆數 */
const PAGE_SIZE = 50

/** 統一縣市字眼（將「臺」替換為「台」） */
function normalizeCity(city: string): string {
    return city ? city.replace(/臺/g, '台') : ''
}

/* === 複合型標記相關型別與工具 === */

/** 群組化後的經銷商資料 */
interface GroupedRetailer {
    /** 用於識別此群組的唯一鍵（以地址為基準） */
    key: string
    /** 代表座標（取第一筆的 lat/lng） */
    lat: number
    lng: number
    /** 地址 */
    address: string
    /** 台彩經銷商（可能為 null） */
    lottery: RetailerData | null
    /** 運彩經銷商（可能為 null） */
    sport: RetailerData | null
    /** 標記類型 */
    type: 'lotteryOnly' | 'sportOnly' | 'combined'
    /** 是否包含 Pro 店家 */
    isPro: boolean
    /** 是否開出過頭獎 */
    isJackpot: boolean
}

/**
 * 將經銷商依地址分組
 * 同一地址若同時有台彩與運彩，合併為 combined 型別
 */
function groupRetailersByAddress(retailers: RetailerData[]): GroupedRetailer[] {
    const addressMap = new Map<string, { lottery: RetailerData | null; sport: RetailerData | null }>()

    for (const r of retailers) {
        if (r.lat == null || r.lng == null) continue
        const key = r.address.trim()
        if (!key) continue

        if (!addressMap.has(key)) {
            addressMap.set(key, { lottery: null, sport: null })
        }
        const group = addressMap.get(key)!
        if (r.source === '台灣彩券') {
            // 若已有台彩資料，保留第一筆
            if (!group.lottery) group.lottery = r
        } else {
            if (!group.sport) group.sport = r
        }
    }

    const result: GroupedRetailer[] = []
    for (const [address, group] of addressMap) {
        const representative = group.lottery || group.sport!
        const type = group.lottery && group.sport
            ? 'combined'
            : group.lottery
                ? 'lotteryOnly'
                : 'sportOnly'
        const isPro = (group.lottery?.merchantTier === 'pro') || (group.sport?.merchantTier === 'pro')
        const isJackpot = ((group.lottery?.jackpotCount || 0) > 0) || ((group.sport?.jackpotCount || 0) > 0)
        result.push({
            key: `${representative.id}-${address}`,
            lat: representative.lat!,
            lng: representative.lng!,
            address,
            lottery: group.lottery,
            sport: group.sport,
            type,
            isPro,
            isJackpot,
        })
    }
    return result
}

/** 台彩主題色 */
const LOTTERY_COLOR = '#F5A623'
/** 運彩主題色 */
const SPORT_COLOR = '#E74C3C'

/**
 *  建立自訂 Leaflet divIcon
 *  - lotteryOnly: 黃色圓形 Pin
 *  - sportOnly:   紅色圓形 Pin
 *  - combined:    上黃下紅雙色膠囊 Pin
 *  - isPro:       金色光暈 + 皇冠標記
 *  - isJackpot:   獎盃標記
 */
function createMarkerIcon(type: GroupedRetailer['type'], isPro = false, isJackpot = false): L.DivIcon {
    const proClass = isPro ? ' marker--pro' : ''
    const jackpotClass = isJackpot ? ' marker--jackpot' : ''
    const proCrown = isPro ? '<span class="marker-pro-crown">👑</span>' : ''
    const jackpotBadge = isJackpot ? '<span class="marker-jackpot-badge">🏆</span>' : ''

    if (type === 'combined') {
        return L.divIcon({
            className: `compound-marker-wrapper${proClass}${jackpotClass}`,
            html: `
                <div class="compound-marker">
                    ${proCrown}
                    ${jackpotBadge}
                    <div class="compound-marker__lottery">🎫</div>
                    <div class="compound-marker__sport">⚽</div>
                    <div class="compound-marker__tail"></div>
                </div>
            `,
            iconSize: [32, 44],
            iconAnchor: [16, 44],
            popupAnchor: [0, -44],
        })
    }

    const color = type === 'lotteryOnly' ? LOTTERY_COLOR : SPORT_COLOR
    const emoji = type === 'lotteryOnly' ? '🎫' : '⚽'
    return L.divIcon({
        className: `single-marker-wrapper${proClass}${jackpotClass}`,
        html: `
            <div class="single-marker" style="background: ${color};">
                ${proCrown}
                ${jackpotBadge}
                <span>${emoji}</span>
                <div class="single-marker__tail" style="border-top-color: ${color};"></div>
            </div>
        `,
        iconSize: [30, 40],
        iconAnchor: [15, 40],
        popupAnchor: [0, -40],
    })
}

/**
 * 單一經銷商 Popup 區段
 * 用於 Popup 內展示一個經銷商的資訊
 */
function RetailerPopupSection({
    retailer,
    themeColor,
    getGoogleMapsUrl,
    openInventoryReport,
    setRatingRetailer,
    officialInventory,
}: {
    retailer: RetailerData
    themeColor: string
    getGoogleMapsUrl: (r: RetailerData) => string
    openInventoryReport: (r: RetailerData) => void
    setRatingRetailer: (r: RetailerData | null) => void
    officialInventory?: MerchantInventoryData[]
}) {
    const isPro = retailer.merchantTier === 'pro'
    const facilities = isPro ? getActiveFacilities(retailer) : []

    return (
        <div className={`compound-popup__section ${isPro ? 'compound-popup__section--pro' : ''}`}>
            <div className="compound-popup__header">
                <strong className="compound-popup__name">
                    {retailer.name}
                    {retailer.jackpotCount && retailer.jackpotCount > 0 ? (
                        <span className="popup-jackpot-badge" title={`已開出 ${retailer.jackpotCount} 次頭獎`}>
                            🏆 {retailer.jackpotCount} 次頭獎
                        </span>
                    ) : null}
                    {isPro && <span className="popup-pro-badge">👑 PRO</span>}
                    {retailer.isClaimed && !isPro && <span className="popup-verified-badge">✅</span>}
                </strong>
                <span
                    className="compound-popup__source-tag"
                    style={{ background: `${themeColor}20`, color: themeColor }}
                >
                    {retailer.source === '台灣彩券' ? '🎫' : '⚽'} {retailer.source}
                </span>
            </div>

            {/* PRO 臨時公告 */}
            {isPro && retailer.announcement && (
                <div className="popup-announcement">
                    📢 {retailer.announcement}
                </div>
            )}

            {/* PRO 設施標籤 */}
            {facilities.length > 0 && (
                <div className="popup-facilities">
                    {facilities.map(f => (
                        <span key={f} className="popup-facility-tag" title={FACILITY_LABELS[f]}>
                            {FACILITY_ICONS[f]}
                        </span>
                    ))}
                </div>
            )}

            {/* 商家官方庫存 */}
            {officialInventory && officialInventory.length > 0 && (
                <div className="popup-official-inventory">
                    <div className="popup-official-inventory__header">
                        <Package size={14} /> 商家官方庫存
                    </div>
                    <div className="popup-official-inventory__grid">
                        {officialInventory.map(item => (
                            <div key={item.itemName} className="official-inventory-item">
                                <span className="official-item-name">{item.itemName}</span>
                                <span className={`official-item-status status--${item.status === '充足' ? 'green' : item.status === '少量' ? 'yellow' : 'red'}`}>
                                    {item.status}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <RatingDisplay retailerId={retailer.id} compact />
            <div className="compound-popup__actions">
                <button
                    onClick={() => openInventoryReport(retailer)}
                    className="compound-popup__btn"
                >
                    📦 庫存
                </button>
                <button
                    onClick={() => setRatingRetailer(retailer)}
                    className="compound-popup__btn"
                >
                    ⭐ 評分
                </button>
                <a
                    href={getGoogleMapsUrl(retailer)}
                    target="_blank"
                    rel="noreferrer"
                    className="compound-popup__nav-btn"
                >
                    🧭 導航
                </a>
                {!retailer.isClaimed && (
                  <Link
                      to={`/merchant/claim/${retailer.id}`}
                      className="compound-popup__btn"
                      style={{ textDecoration: 'none', background: '#e0f2fe', color: '#0369a1' }}
                  >
                      🙋‍♂️ 認領
                  </Link>
                )}
            </div>
        </div>
    )
}

/**
 * 叢集化地圖標記元件
 * 使用 MarkerClusterGroup 取代手動的視窗篩選
 * 同地址的台彩/運彩合併為複合型標記
 */
function ClusteredMarkers({
    retailers,
    getGoogleMapsUrl,
    openInventoryReport,
    setRatingRetailer,
    officialInventoryCache,
    onMarkerClick,
}: {
    retailers: RetailerData[]
    getGoogleMapsUrl: (r: RetailerData) => string
    openInventoryReport: (r: RetailerData) => void
    setRatingRetailer: (r: RetailerData | null) => void
    officialInventoryCache: Record<number, MerchantInventoryData[]>
    onMarkerClick: (retailers: RetailerData[]) => void
}) {
    // 將經銷商依地址分組，同地址合併
    const grouped = useMemo(() => groupRetailersByAddress(retailers), [retailers])

    return (
        <MarkerClusterGroup
            chunkedLoading
            maxClusterRadius={60}
            spiderfyOnMaxZoom
            showCoverageOnHover={false}
            // NOTE: leaflet.markercluster 的型別定義在 @types/leaflet 未完全匯出，使用 any
            iconCreateFunction={(cluster: any) => {
                const count = cluster.getChildCount()
                let sizeClass = 'marker-cluster-small'
                if (count >= 100) sizeClass = 'marker-cluster-large'
                else if (count >= 10) sizeClass = 'marker-cluster-medium'
                return L.divIcon({
                    html: `<div><span>${count}</span></div>`,
                    className: `marker-cluster ${sizeClass} marker-cluster--gold`,
                    iconSize: L.point(40, 40),
                })
            }}
        >
            {grouped.map(g => (
                <Marker
                    key={g.key}
                    position={[g.lat, g.lng]}
                    icon={createMarkerIcon(g.type, g.isPro, g.isJackpot)}
                    zIndexOffset={g.isPro || g.isJackpot ? 1000 : 0}
                    eventHandlers={{
                        click: () => {
                            const rs = []
                            if (g.lottery) rs.push(g.lottery)
                            if (g.sport) rs.push(g.sport)
                            onMarkerClick(rs)
                        }
                    }}
                >
                    <Popup minWidth={240} maxWidth={320}>
                        <div className="compound-popup">
                            {/* 地址（所有型別共用） */}
                            <div className="compound-popup__address">
                                📍 {g.address}
                            </div>

                            {/* 台彩區段 */}
                            {g.lottery && (
                                <RetailerPopupSection
                                    retailer={g.lottery}
                                    themeColor={LOTTERY_COLOR}
                                    getGoogleMapsUrl={getGoogleMapsUrl}
                                    openInventoryReport={openInventoryReport}
                                    setRatingRetailer={setRatingRetailer}
                                    officialInventory={officialInventoryCache[g.lottery.id]}
                                />
                            )}

                            {/* 分隔線（僅複合型有） */}
                            {g.type === 'combined' && (
                                <div className="compound-popup__divider" />
                            )}

                            {/* 運彩區段 */}
                            {g.sport && (
                                <RetailerPopupSection
                                    retailer={g.sport}
                                    themeColor={SPORT_COLOR}
                                    getGoogleMapsUrl={getGoogleMapsUrl}
                                    openInventoryReport={openInventoryReport}
                                    setRatingRetailer={setRatingRetailer}
                                    officialInventory={officialInventoryCache[g.sport.id]}
                                />
                            )}
                        </div>
                    </Popup>
                </Marker>
            ))}
        </MarkerClusterGroup>
    )
}

export default function CommunityMap() {
    // 使用者 Karma
    const { user } = useUser()

    // 經銷商
    const [retailers, setRetailers] = useState<RetailerData[]>([])
    const [loadingRetailers, setLoadingRetailers] = useState(true)
    const [search, setSearch] = useState('')
    const [filterCity, setFilterCity] = useState('')
    const [filterDistrict, setFilterDistrict] = useState('')
    const [filterSource, setFilterSource] = useState('全部')
    const [showFilters, setShowFilters] = useState(false)
    const [activeTags, setActiveTags] = useState<string[]>([])
    const [showTagFilters, setShowTagFilters] = useState(false)
    const [displayCount, setDisplayCount] = useState(PAGE_SIZE)
    const [viewMode, setViewMode] = useState<'list' | 'map'>('list')
    const [heatmapPoints, setHeatmapPoints] = useState<HeatmapPoint[]>([])

    // 點擊次數追蹤
    const handleRetailerClick = useCallback((retailerId: number) => {
        recordRetailerClick(retailerId).catch(() => {})
    }, [])

    const handleMarkerClick = useCallback((rs: RetailerData[]) => {
        rs.forEach(r => handleRetailerClick(r.id))
    }, [handleRetailerClick])

    // 打卡
    const [checkins, setCheckins] = useState<CheckinData[]>([])
    const [city, setCity] = useState('')
    const [amount, setAmount] = useState('')
    const [gameName, setGameName] = useState('')
    const [submitting, setSubmitting] = useState(false)
    const [showCheckin, setShowCheckin] = useState(false)

    // 庫存回報
    const [showInventoryReport, setShowInventoryReport] = useState(false)
    const [inventoryRetailer, setInventoryRetailer] = useState<RetailerData | null>(null)
    const [inventoryItem, setInventoryItem] = useState('')
    const [inventoryStatus, setInventoryStatus] = useState('')
    const [reportingInventory, setReportingInventory] = useState(false)
    // 回報款式搜尋
    const [reportSearchInput, setReportSearchInput] = useState('')
    const [reportSearchResults, setReportSearchResults] = useState<ScratchcardSearchItem[]>([])
    const [reportSearchLoading, setReportSearchLoading] = useState(false)

    // 庫存快取（retailerId -> items）
    const [inventoryCache, setInventoryCache] = useState<Record<number, InventoryItem[]>>({})
    // 商家官方庫存快取
    const [officialInventoryCache, setOfficialInventoryCache] = useState<Record<number, MerchantInventoryData[]>>({})

    // 節慶模式
    const [festival, setFestival] = useState<FestivalStatus | null>(null)

    // 評分 Modal
    const [ratingRetailer, setRatingRetailer] = useState<RetailerData | null>(null)

    useEffect(() => {
        loadData()
    }, [])

    async function loadData() {
        try {
            setLoadingRetailers(true)
            const [retData, chkData, festData, heatData] = await Promise.all([
                fetchRetailers(),
                fetchCheckins(),
                fetchFestivalStatus().catch(() => null),
                fetchHeatmap().catch(() => [])
            ])
            setRetailers(retData)
            setCheckins(chkData)
            if (festData) setFestival(festData)
            setHeatmapPoints(heatData)

            // 如果有認領的店家，預載他們的官方庫存（優化體驗）
            const claimedIds = retData.filter(r => r.isClaimed).map(r => r.id)
            if (claimedIds.length > 0) {
                // 批次獲取（簡單起見先前 10 個或只取可見的，這裡先實作一個基本的預載）
                claimedIds.slice(0, 20).forEach(async (id) => {
                    try {
                        const data = await fetchMerchantOfficialInventory(id)
                        setOfficialInventoryCache(prev => ({ ...prev, [id]: data.items }))
                    } catch { }
                })
            }
        } catch {
            setRetailers([])
            setCheckins([])
        } finally {
            setLoadingRetailers(false)
        }
    }

    /** 可選鄉鎮市區 */
    const availableDistricts = useMemo(() => {
        if (!filterCity) return []
        const normFilter = normalizeCity(filterCity)
        const districts = retailers
            .filter(r => normalizeCity(r.city) === normFilter && r.district)
            .map(r => r.district)
        return Array.from(new Set(districts)).sort()
    }, [retailers, filterCity])

    /** 篩選後的經銷商 */
    const filtered = useMemo(() => {
        let result = [...retailers]

        // 搜尋
        if (search) {
            const kw = search.toLowerCase()
            result = result.filter(r =>
                r.name.toLowerCase().includes(kw) ||
                r.address.toLowerCase().includes(kw)
            )
        }

        // 縣市篩選
        if (filterCity) {
            const normFilter = normalizeCity(filterCity)
            result = result.filter(r => normalizeCity(r.city) === normFilter)
        }

        // 鄉鎮市區篩選
        if (filterDistrict) {
            result = result.filter(r => r.district === filterDistrict)
        }

        // 來源篩選
        if (filterSource !== '全部') {
            result = result.filter(r => r.source === filterSource)
        }

        // 設施標籤篩選
        if (activeTags.length > 0) {
            result = result.filter(r =>
                activeTags.every(tag => (r as unknown as Record<string, boolean>)[tag])
            )
        }

        // Pro 店家置頂排序
        result.sort((a, b) => {
            const aPro = a.merchantTier === 'pro' ? 1 : 0
            const bPro = b.merchantTier === 'pro' ? 1 : 0
            return bPro - aPro
        })

        return result
    }, [retailers, search, filterCity, filterDistrict, filterSource, activeTags])

    /** 各縣市統計 */
    const cityStats = useMemo(() => {
        const stats: Record<string, { lottery: number; sport: number; total: number }> = {}
        retailers.forEach(r => {
            const normCity = normalizeCity(r.city)
            if (!stats[normCity]) stats[normCity] = { lottery: 0, sport: 0, total: 0 }
            stats[normCity].total++
            if (r.source === '台灣彩券') stats[normCity].lottery++
            else stats[normCity].sport++
        })
        return stats
    }, [retailers])

    /** 打卡統計 */
    const checkinStats = checkins.reduce<Record<string, { count: number; total: number }>>((acc, c) => {
        const normCity = normalizeCity(c.city)
        if (!acc[normCity]) acc[normCity] = { count: 0, total: 0 }
        acc[normCity].count++
        acc[normCity].total += c.amount
        return acc
    }, {})

    /** Google Maps 搜尋連結 */
    function getGoogleMapsUrl(r: RetailerData) {
        const q = encodeURIComponent(`${r.name} ${r.address}`)
        return `https://www.google.com/maps/search/${q}`
    }

    /** 切換設施標籤篩選 */
    function toggleTag(tag: string) {
        setActiveTags(prev =>
            prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
        )
    }

    /** 打卡送出 */
    async function handleSubmit() {
        if (!city || !amount) return
        setSubmitting(true)
        try {
            const newCheckin = await createCheckin({
                city,
                amount: Number(amount),
                gameName,
            })
            setCheckins([newCheckin, ...checkins])
            setCity('')
            setAmount('')
            setGameName('')
        } catch {
            // 靜默處理
        } finally {
            setSubmitting(false)
        }
    }

    /** 開啟庫存回報面板 */
    function openInventoryReport(r: RetailerData) {
        setInventoryRetailer(r)
        setInventoryItem('')
        setInventoryStatus('')
        setReportSearchInput('')
        setShowInventoryReport(true)
        // 預載全部未過期款式
        setReportSearchLoading(true)
        searchScratchcardsPublic('').then(setReportSearchResults).finally(() => setReportSearchLoading(false))
    }

    /** 送出庫存回報 */
    async function handleInventoryReport() {
        if (!inventoryRetailer || !inventoryItem || !inventoryStatus || !user) return
        setReportingInventory(true)
        try {
            // 嘗試取得 GPS 座標（用於距離驗證）
            let lat: number | undefined
            let lng: number | undefined
            if (navigator.geolocation) {
                try {
                    const pos = await new Promise<GeolocationPosition>((resolve, reject) =>
                        navigator.geolocation.getCurrentPosition(resolve, reject, { timeout: 5000 })
                    )
                    lat = pos.coords.latitude
                    lng = pos.coords.longitude
                } catch {
                    // GPS 失敗不阻止回報
                }
            }
            await reportInventory({
                retailerId: inventoryRetailer.id,
                userId: user.id,
                item: inventoryItem,
                status: inventoryStatus,
                lat,
                lng,
            })
            // 更新庫存快取
            loadInventoryForRetailer(inventoryRetailer.id)
            setShowInventoryReport(false)
        } catch {
            // 靜默處理
        } finally {
            setReportingInventory(false)
        }
    }

    /** 載入某店家庫存 */
    const loadInventoryForRetailer = useCallback(async (retailerId: number) => {
        try {
            const data = await fetchInventory(retailerId)
            setInventoryCache(prev => ({ ...prev, [retailerId]: data.items }))
        } catch {
            // 靜默處理
        }
    }, [])

    /** 載入更多 */
    function handleLoadMore() {
        setDisplayCount(prev => prev + PAGE_SIZE)
    }

    // 重設 displayCount 當篩選條件改變
    useEffect(() => {
        setDisplayCount(PAGE_SIZE)
    }, [search, filterCity, filterDistrict, filterSource, activeTags])

    const displayedRetailers = filtered.slice(0, displayCount)
    const hasMore = displayCount < filtered.length

    return (
        <div className="community-map">
            <SeoHead
                title="經銷商地圖 — 全台彩券行搜尋與庫存查詢"
                description="搜尋全台彩券經銷商，查看設施標籤、庫存狀態、營業資訊與導航。支援地圖模式與列表模式切換。"
                path="/map"
                jsonLd={{
                    '@context': 'https://schema.org',
                    '@type': 'LocalBusiness',
                    name: '台灣彩券經銷商',
                    description: '全台台灣彩券與運動彩券經銷商地圖，提供庫存查詢、設施標籤與導航功能。',
                    geo: { '@type': 'GeoCoordinates', latitude: 23.6978, longitude: 120.9605 },
                }}
            />
            {/* Hero */}
            <section className="community-map__hero">
                <motion.div
                    className="community-map__hero-content"
                    initial={{ opacity: 0, y: 30 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6 }}
                >
                    <h1 className="community-map__title">
                        <MapPin size={32} />
                        財神到 — 社群地圖
                    </h1>
                    <p className="community-map__subtitle">
                        全台 {retailers.length.toLocaleString()} 間彩券行 · 搜尋附近的投注站
                    </p>
                    {/* Karma 等級徽章 */}
                    {user && (
                        <div className="community-map__karma-badge">
                            <Star size={14} style={{ color: LEVEL_COLORS[user.karmaLevel - 1] }} />
                            <span style={{ color: LEVEL_COLORS[user.karmaLevel - 1] }}>Lv.{user.karmaLevel}</span>
                            <span className="community-map__karma-title">{user.levelTitle}</span>
                            <span className="community-map__karma-pts">{user.karmaPoints} 積分</span>
                        </div>
                    )}
                </motion.div>
            </section>

            {/* 節慶快報 Banner */}
            <AnimatePresence>
                {festival?.isActive && (
                    <motion.section
                        className="community-map__festival-banner"
                        initial={{ opacity: 0, y: -20 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -20 }}
                    >
                        <PartyPopper size={20} />
                        <div className="community-map__festival-info">
                            <strong>{festival.name}</strong>
                            <span>{festival.description}</span>
                        </div>
                        <Flame size={18} className="community-map__festival-flame" />
                    </motion.section>
                )}
            </AnimatePresence>

            <div className="community-map__content container">
                {/* 搜尋 + 篩選 */}
                <motion.section
                    className="community-map__search-section"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                >
                    <div className="community-map__search-bar">
                        <Search size={18} />
                        <input
                            type="text"
                            placeholder="搜尋投注站名稱或地址..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                        {search && (
                            <button className="community-map__clear-btn" onClick={() => setSearch('')}>
                                <X size={16} />
                            </button>
                        )}
                    </div>

                    <div className="community-map__filter-row">
                        {/* 來源切換 */}
                        <div className="community-map__source-tabs">
                            {SOURCES.map(src => (
                                <button
                                    key={src}
                                    className={`community-map__source-tab ${filterSource === src ? 'community-map__source-tab--active' : ''}`}
                                    onClick={() => setFilterSource(src)}
                                >
                                    {src === '全部' ? '🎰 全部' : src === '台灣彩券' ? '🎫 台彩' : '⚽ 運彩'}
                                </button>
                            ))}
                        </div>

                        {/* 篩選按鈕 */}
                        <button
                            className="community-map__filter-btn"
                            onClick={() => setShowFilters(!showFilters)}
                        >
                            <Filter size={16} />
                            縣市篩選
                            <ChevronDown size={14} className={showFilters ? 'rotate-180' : ''} />
                        </button>

                        {/* 設施篩選 */}
                        <button
                            className={`community-map__filter-btn ${activeTags.length > 0 ? 'community-map__filter-btn--active' : ''}`}
                            onClick={() => setShowTagFilters(!showTagFilters)}
                        >
                            <Package size={16} />
                            設施篩選 {activeTags.length > 0 && `(${activeTags.length})`}
                        </button>

                        {/* 打卡按鈕 */}
                        <button
                            className="community-map__checkin-toggle"
                            onClick={() => setShowCheckin(!showCheckin)}
                        >
                            <Send size={16} />
                            中獎打卡
                        </button>
                    </div>

                    {/* 縣市篩選面板 */}
                    <AnimatePresence>
                        {showFilters && (
                            <motion.div
                                className="community-map__city-filter"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                            >
                                <button
                                    className={`community-map__city-chip ${!filterCity ? 'community-map__city-chip--active' : ''}`}
                                    onClick={() => { setFilterCity(''); setFilterDistrict(''); }}
                                >
                                    全部縣市
                                </button>
                                {CITIES.map(c => (
                                    <button
                                        key={c}
                                        className={`community-map__city-chip ${filterCity === c ? 'community-map__city-chip--active' : ''}`}
                                        onClick={() => { setFilterCity(c); setFilterDistrict(''); }}
                                    >
                                        {c}
                                        {cityStats[c] && (
                                            <span className="community-map__city-count">{cityStats[c].total}</span>
                                        )}
                                    </button>
                                ))}

                                {/* 鄉鎮市區篩選 (縣市有選定時才出現) */}
                                {filterCity && availableDistricts.length > 0 && (
                                    <div className="community-map__district-filter" style={{ width: '100%', marginTop: '0.5rem', borderTop: '1px dashed var(--border-subtle)', paddingTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                                        <button
                                            className={`community-map__city-chip ${!filterDistrict ? 'community-map__city-chip--active' : ''}`}
                                            onClick={() => setFilterDistrict('')}
                                        >
                                            全部區域
                                        </button>
                                        {availableDistricts.map(d => {
                                            const districtCount = retailers.filter(r => normalizeCity(r.city) === normalizeCity(filterCity) && r.district === d).length;
                                            return (
                                                <button
                                                    key={d}
                                                    className={`community-map__city-chip ${filterDistrict === d ? 'community-map__city-chip--active' : ''}`}
                                                    onClick={() => setFilterDistrict(d)}
                                                >
                                                    {d}
                                                    <span className="community-map__city-count">{districtCount}</span>
                                                </button>
                                            )
                                        })}
                                    </div>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* 設施標籤篩選面板 */}
                    <AnimatePresence>
                        {showTagFilters && (
                            <motion.div
                                className="community-map__tag-filter"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                            >
                                <div className="community-map__tag-chips">
                                    {TAG_FILTERS.map(t => (
                                        <button
                                            key={t.key}
                                            className={`community-map__tag-chip ${activeTags.includes(t.key) ? 'community-map__tag-chip--active' : ''}`}
                                            onClick={() => toggleTag(t.key)}
                                        >
                                            {t.label}
                                        </button>
                                    ))}
                                </div>
                                {activeTags.length > 0 && (
                                    <button
                                        className="community-map__tag-clear"
                                        onClick={() => setActiveTags([])}
                                    >
                                        <X size={14} /> 清除篩選
                                    </button>
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* 打卡表單 */}
                    <AnimatePresence>
                        {showCheckin && (
                            <motion.div
                                className="community-map__checkin-form glass-card"
                                initial={{ opacity: 0, height: 0 }}
                                animate={{ opacity: 1, height: 'auto' }}
                                exit={{ opacity: 0, height: 0 }}
                            >
                                <h3><MapPin size={18} /> 回報中獎</h3>
                                <div className="community-map__form-row">
                                    <select value={city} onChange={(e) => setCity(e.target.value)}>
                                        <option value="">選擇縣市</option>
                                        {CITIES.map(c => (
                                            <option key={c} value={c}>{c}</option>
                                        ))}
                                    </select>
                                    <input
                                        type="number"
                                        placeholder="中獎金額"
                                        value={amount}
                                        onChange={(e) => setAmount(e.target.value)}
                                    />
                                    <input
                                        placeholder="款式名稱（選填）"
                                        value={gameName}
                                        onChange={(e) => setGameName(e.target.value)}
                                    />
                                    <button
                                        className="community-map__submit-btn"
                                        onClick={handleSubmit}
                                        disabled={submitting || !city || !amount}
                                    >
                                        <Send size={14} />
                                        {submitting ? '送出中...' : '送出打卡'}
                                    </button>
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>
                </motion.section>

                {/* 統計摘要 */}
                <motion.section
                    className="community-map__stats-row"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.15 }}
                >
                    <div className="community-map__stat glass-card">
                        <Store size={20} />
                        <div>
                            <span>彩券行</span>
                            <strong>{retailers.filter(r => r.source === '台灣彩券').length.toLocaleString()}</strong>
                        </div>
                    </div>
                    <div className="community-map__stat glass-card">
                        <Store size={20} />
                        <div>
                            <span>運彩行</span>
                            <strong>{retailers.filter(r => r.source === '台灣運彩').length.toLocaleString()}</strong>
                        </div>
                    </div>
                    <div className="community-map__stat glass-card">
                        <Navigation size={20} />
                        <div>
                            <span>搜尋結果</span>
                            <strong>{filtered.length.toLocaleString()}</strong>
                        </div>
                    </div>
                    <div className="community-map__stat glass-card">
                        <Flame size={20} />
                        <div>
                            <span>中獎回報</span>
                            <strong>{checkins.length}</strong>
                        </div>
                    </div>
                </motion.section>

                <div className="community-map__main-layout">
                    {/* 經銷商列表 */}
                    <section className="community-map__retailers">
                        <div className="community-map__list-header">
                            <div className="community-map__list-title-row">
                                <h2>🏪 投注站列表</h2>
                                <div className="community-map__view-toggled">
                                    <button
                                        className={`community-map__view-btn ${viewMode === 'list' ? 'active' : ''}`}
                                        onClick={() => setViewMode('list')}
                                    >
                                        <List size={16} /> 列表
                                    </button>
                                    <button
                                        className={`community-map__view-btn ${viewMode === 'map' ? 'active' : ''}`}
                                        onClick={() => setViewMode('map')}
                                    >
                                        <MapIcon size={16} /> 地圖
                                    </button>
                                </div>
                            </div>
                            <span className="community-map__result-count">
                                顯示 {displayedRetailers.length} / {filtered.length} 間
                            </span>
                        </div>

                        {loadingRetailers ? (
                            <div className="community-map__loading">
                                <div className="spinner" />
                                <p>載入經銷商資料中...</p>
                            </div>
                        ) : filtered.length === 0 ? (
                            <div className="community-map__empty">
                                <Store size={48} />
                                <p>找不到符合條件的投注站</p>
                            </div>
                        ) : viewMode === 'map' ? (
                            <div className="community-map__map-view glass-card" style={{ padding: 0, overflow: 'hidden' }}>
                                <MapContainer
                                    center={[23.6978, 120.9605]}
                                    zoom={7}
                                    style={{ height: '700px', width: '100%', zIndex: 0 }}
                                >
                                    <TileLayer
                                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                                        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                                    />
                                    {heatmapPoints.length > 0 && <HeatmapLayer points={heatmapPoints} />}

                                    <ClusteredMarkers
                                        retailers={filtered}
                                        getGoogleMapsUrl={getGoogleMapsUrl}
                                        openInventoryReport={openInventoryReport}
                                        setRatingRetailer={setRatingRetailer}
                                        officialInventoryCache={officialInventoryCache}
                                        onMarkerClick={handleMarkerClick}
                                    />
                                </MapContainer>
                            </div>
                        ) : (
                            <>
                                <div className="community-map__retailer-grid">
                                    {displayedRetailers.map((r, idx) => (
                                        <motion.div
                                            key={r.id}
                                            className={`community-map__retailer-card glass-card ${r.merchantTier === 'pro' ? 'community-map__retailer-card--pro' : ''}`}
                                            onClick={() => handleRetailerClick(r.id)}
                                            initial={{ opacity: 0, y: 10 }}
                                            animate={{ opacity: 1, y: 0 }}
                                            transition={{ delay: Math.min(idx * 0.02, 0.5) }}
                                        >
                                            <div className="community-map__retailer-header">
                                                <h3 className="community-map__retailer-name">
                                                    {r.name}
                                                    {/* 頭獎標章 */}
                                                    {r.jackpotCount && r.jackpotCount > 0 ? (
                                                        <span className="community-map__badge community-map__badge--jackpot" title={`已開出 ${r.jackpotCount} 次頭獎`}>
                                                            🏆 {r.jackpotCount} 次頭獎
                                                        </span>
                                                    ) : null}
                                                    {/* 認證徽章 */}
                                                    {r.isClaimed && (
                                                        <span className="community-map__badge community-map__badge--verified" title="已認證店家">
                                                            <Shield size={12} /> 認證
                                                        </span>
                                                    )}
                                                    {r.merchantTier === 'pro' && (
                                                        <span className="community-map__badge community-map__badge--pro" title="專業版店家">
                                                            <Star size={12} /> PRO
                                                        </span>
                                                    )}
                                                </h3>
                                                <span className={`community-map__retailer-source ${r.source === '台灣彩券' ? 'community-map__retailer-source--lottery' : 'community-map__retailer-source--sport'}`}>
                                                    {r.source === '台灣彩券' ? '🎫' : '⚽'} {r.source}
                                                </span>
                                            </div>

                                            {/* 臨時公告 */}
                                            {r.announcement && (
                                                <div className="community-map__announcement">
                                                    <Megaphone size={14} />
                                                    <span>{r.announcement}</span>
                                                </div>
                                            )}

                                            {/* PRO 設施標籤列 */}
                                            {r.merchantTier === 'pro' && getActiveFacilities(r).length > 0 && (
                                                <div className="community-map__facility-tags">
                                                    {getActiveFacilities(r).map(f => (
                                                        <span key={f} className="community-map__facility-tag" title={FACILITY_LABELS[f]}>
                                                            {FACILITY_ICONS[f]} {FACILITY_LABELS[f]}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}

                                            <p className="community-map__retailer-address">
                                                <MapPin size={14} />
                                                {r.address}
                                            </p>

                                            {/* 庫存燈號 */}
                                            {inventoryCache[r.id] && inventoryCache[r.id].length > 0 && (
                                                <div className="community-map__inventory-lights">
                                                    {inventoryCache[r.id].map(inv => (
                                                        <span
                                                            key={inv.item}
                                                            className={`community-map__inv-dot community-map__inv-dot--${inv.status === '充足' ? 'green' : inv.status === '少量' ? 'yellow' : 'red'}`}
                                                            title={`${inv.item}: ${inv.status}`}
                                                        >
                                                            {inv.item.replace('元刮刮樂', '')}
                                                        </span>
                                                    ))}
                                                </div>
                                            )}

                                            <div className="community-map__retailer-meta">
                                                <span className="community-map__retailer-district">
                                                    {r.city} · {r.district}
                                                </span>
                                                <div className="community-map__retailer-actions">
                                                    <button
                                                        className="community-map__report-btn"
                                                        onClick={() => openInventoryReport(r)}
                                                        title="回報庫存"
                                                    >
                                                        <Package size={13} /> 庫存
                                                    </button>
                                                    <button
                                                        className="community-map__report-btn"
                                                        onClick={() => setRatingRetailer(r)}
                                                        title="評分"
                                                    >
                                                        <Star size={13} /> 評分
                                                    </button>
                                                    <a
                                                        href={getGoogleMapsUrl(r)}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="community-map__map-link"
                                                    >
                                                        <ExternalLink size={14} />
                                                        導航
                                                    </a>
                                                    {!r.isClaimed && (
                                                        <Link
                                                            to={`/merchant/claim/${r.id}`}
                                                            className="community-map__report-btn"
                                                            style={{ textDecoration: 'none', background: '#e0f2fe', color: '#0369a1', whiteSpace: 'nowrap' }}
                                                        >
                                                            🙋‍♂️ 認領
                                                        </Link>
                                                    )}
                                                </div>
                                            </div>

                                            {/* 評分星等 */}
                                            <RatingDisplay retailerId={r.id} compact />
                                        </motion.div>
                                    ))}
                                </div>

                                {hasMore && (
                                    <button className="community-map__load-more" onClick={handleLoadMore}>
                                        載入更多（還有 {filtered.length - displayCount} 間）
                                    </button>
                                )}
                            </>
                        )}
                    </section>

                    {/* 側邊：熱區 + 最新打卡 */}
                    <aside className="community-map__sidebar">
                        {/* 全台熱區 */}
                        <div className="community-map__heatmap glass-card">
                            <h3><Flame size={18} /> 全台中獎熱區</h3>
                            <div className="community-map__heatmap-grid">
                                {CITIES.map(c => {
                                    const stat = checkinStats[c]
                                    return (
                                        <div
                                            key={c}
                                            className={`community-map__heat-item ${stat ? 'community-map__heat-item--active' : ''}`}
                                            onClick={() => { setFilterCity(c); setShowFilters(true) }}
                                        >
                                            <span>{c}</span>
                                            {stat ? (
                                                <strong>${stat.total.toLocaleString()}</strong>
                                            ) : (
                                                <span className="community-map__heat-empty">—</span>
                                            )}
                                        </div>
                                    )
                                })}
                            </div>
                        </div>

                        {/* 最新打卡 */}
                        {checkins.length > 0 && (
                            <div className="community-map__recent glass-card">
                                <h3>📋 最新打卡</h3>
                                {checkins.slice(0, 10).map(c => (
                                    <div key={c.id} className="community-map__checkin-item">
                                        <MapPin size={14} />
                                        <span className="community-map__checkin-city">{c.city}</span>
                                        <span className="community-map__checkin-amount">${c.amount.toLocaleString()}</span>
                                        {c.gameName && (
                                            <span className="community-map__checkin-game">{c.gameName}</span>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </aside>
                </div>
            </div>

            {/* 庫存回報 Modal */}
            <AnimatePresence>
                {showInventoryReport && inventoryRetailer && (
                    <motion.div
                        className="community-map__modal-overlay"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={() => setShowInventoryReport(false)}
                    >
                        <motion.div
                            className="community-map__modal glass-card"
                            initial={{ opacity: 0, scale: 0.9 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.9 }}
                            onClick={(e) => e.stopPropagation()}
                        >
                            <div className="community-map__modal-header">
                                <h3><Package size={18} /> 回報庫存</h3>
                                <button onClick={() => setShowInventoryReport(false)}><X size={18} /></button>
                            </div>
                            <p className="community-map__modal-store">
                                <Store size={14} /> {inventoryRetailer.name}
                            </p>

                            {/* 品項搜尋 */}
                            <div className="community-map__modal-section">
                                <label>搜尋刮刮樂款式（名稱或期數）</label>
                                <input
                                    type="text"
                                    className="community-map__report-search"
                                    placeholder="輸入款式名稱或期數..."
                                    value={reportSearchInput}
                                    onChange={async (e) => {
                                        const val = e.target.value
                                        setReportSearchInput(val)
                                        setReportSearchLoading(true)
                                        try {
                                            const results = await searchScratchcardsPublic(val)
                                            setReportSearchResults(results)
                                        } catch { setReportSearchResults([]) }
                                        finally { setReportSearchLoading(false) }
                                    }}
                                />
                                <div className="community-map__report-results">
                                    {reportSearchLoading && <div className="community-map__report-loading">搜尋中...</div>}
                                    {!reportSearchLoading && reportSearchResults.length === 0 && (
                                        <div className="community-map__report-empty">沒有找到符合的款式</div>
                                    )}
                                    {!reportSearchLoading && reportSearchResults.map(card => (
                                        <button
                                            key={card.id}
                                            className={`community-map__report-item ${inventoryItem === `${card.name} ($${card.price})` ? 'community-map__report-item--active' : ''}`}
                                            onClick={() => setInventoryItem(`${card.name} ($${card.price})`)}
                                        >
                                            {card.imageUrl && <img src={card.imageUrl} alt={card.name} className="community-map__report-item-img" />}
                                            <div className="community-map__report-item-info">
                                                <span className="community-map__report-item-name">{card.name}</span>
                                                <span className="community-map__report-item-meta">期數 {card.gameId} ・${card.price}</span>
                                            </div>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* 狀態選擇 */}
                            <div className="community-map__modal-section">
                                <label>庫存狀態</label>
                                <div className="community-map__modal-options">
                                    {INVENTORY_STATUS.map(s => (
                                        <button
                                            key={s.value}
                                            className={`community-map__modal-opt ${inventoryStatus === s.value ? 'community-map__modal-opt--active' : ''}`}
                                            onClick={() => setInventoryStatus(s.value)}
                                            style={inventoryStatus === s.value ? { borderColor: s.color, color: s.color } : {}}
                                        >
                                            {s.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            <button
                                className="community-map__modal-submit"
                                onClick={handleInventoryReport}
                                disabled={reportingInventory || !inventoryItem || !inventoryStatus || !user}
                            >
                                <Send size={14} />
                                {reportingInventory ? '送出中...' : '送出回報'}
                            </button>
                            <p className="community-map__modal-hint">
                                📍 系統將自動取得您的 GPS 位置以驗證距離
                            </p>
                        </motion.div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* 評分 Modal */}
            {ratingRetailer && (
                <RatingPanel
                    retailerId={ratingRetailer.id}
                    retailerName={ratingRetailer.name}
                    onClose={() => setRatingRetailer(null)}
                    onSubmitted={() => setRatingRetailer(null)}
                />
            )}
        </div>
    )
}
