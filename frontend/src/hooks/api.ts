/**
 * API 服務封裝
 * 集中管理所有 API 請求
 */
import axios from 'axios'

/** API 基底 URL（開發環境指向本地 FastAPI） */
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const api = axios.create({
    baseURL: API_BASE,
    timeout: 20000,
})

/* === 型別定義 === */

/** 獎金結構 */
export interface PrizeStructure {
    prizeName: string
    prizeAmount: number
    totalCount: number
    perBookDesc: string
}

/** 列表項目 */
export interface ScratchcardListItem {
    id: number
    gameId: string
    name: string
    price: number
    maxPrize: string
    maxPrizeAmount: number
    salesRate: string
    salesRateValue: number
    grandPrizeCount: number
    grandPrizeUnclaimed: number
    isHighWinRate: boolean
    isPreview: boolean
    issueDate: string
    endDate: string
    overallWinRate: string
    imageUrl: string
    redeemDeadline: string
}

/** 詳情 */
export interface ScratchcardDetail extends ScratchcardListItem {
    redeemDeadline: string
    totalIssued: number
    prizeInfoUrl: string
    prizes: PrizeStructure[]
}

/** 打卡 */
export interface CheckinData {
    id: number
    city: string
    amount: number
    gameName: string
    createdAt: string
}

/** YouTube 影片 */
export interface YouTubeVideo {
    id: number
    title: string
    url: string
    thumbnailUrl: string
    gameId: string
}

/* === API 函式 === */

/**
 * 取得刮刮樂列表
 */
export async function fetchScratchcards(params?: {
    sortBy?: string
    order?: string
    price?: number
    highWinOnly?: boolean
    isPreview?: boolean
}): Promise<ScratchcardListItem[]> {
    const { data } = await api.get('/api/scratchcards', {
        params: {
            sort_by: params?.sortBy,
            order: params?.order,
            price: params?.price,
            high_win_only: params?.highWinOnly,
            is_preview: params?.isPreview,
        },
    })
    return data
}

/**
 * 取得預告（即將發售）刮刮樂列表
 */
export async function fetchPreviewScratchcards(): Promise<ScratchcardListItem[]> {
    return fetchScratchcards({ isPreview: true, sortBy: 'issueDate', order: 'asc' })
}

/**
 * 取得刮刮樂詳情
 */
export async function fetchScratchcardDetail(id: number): Promise<ScratchcardDetail> {
    const { data } = await api.get(`/api/scratchcards/${id}`)
    return data
}

/**
 * 取得 YouTube 影片列表
 */
export async function fetchVideos(): Promise<YouTubeVideo[]> {
    const { data } = await api.get('/api/videos')
    return data
}

/**
 * 取得打卡紀錄
 */
export async function fetchCheckins(): Promise<CheckinData[]> {
    const { data } = await api.get('/api/map/checkins')
    return data
}

/**
 * 新增打卡
 */
export async function createCheckin(payload: {
    city: string
    amount: number
    gameName?: string
}): Promise<CheckinData> {
    const { data } = await api.post('/api/map/checkin', payload)
    return data
}

/* === 經銷商 (Retailer) === */

/** 經銷商資料 */
export interface RetailerData {
    id: number
    name: string
    address: string
    city: string
    district: string
    source: string
    lat: number | null
    lng: number | null
    isActive: boolean
    // Phase 3：設施標籤
    hasAC: boolean
    hasToilet: boolean
    hasSeats: boolean
    hasWifi: boolean
    hasAccessibility: boolean
    hasEPay: boolean
    hasStrategy: boolean
    hasNumberPick: boolean
    hasScratchBoard: boolean
    hasMagnifier: boolean
    hasReadingGlasses: boolean
    hasNewspaper: boolean
    hasSportTV: boolean
    // Phase 3：認領
    isClaimed: boolean
    merchantTier: string
    announcement: string
    // Phase 4
    jackpotCount: number
}

/**
 * 取得經銷商列表
 * @param params 篩選參數
 */
export async function fetchRetailers(params?: {
    city?: string
    source?: string
    search?: string
    has_coords?: boolean
    exclude_ids?: string
}): Promise<RetailerData[]> {
    const { data } = await api.get('/api/retailers', { params })
    return data
}

/**
 * 取得附近經銷商（依距離排序）
 */
export async function fetchNearbyRetailers(
    lat: number,
    lng: number,
    radiusKm?: number,
    limit?: number
): Promise<RetailerData[]> {
    const { data } = await api.get('/api/retailers/nearby', {
        params: { lat, lng, radius_km: radiusKm || 5, limit: limit || 50 },
    })
    return data
}

/** 地圖標記輕量資料 */
export interface MapMarkerData {
    id: number
    name: string
    lat: number | null
    lng: number | null
    city: string
    district: string
    source: string
    address: string
    isClaimed: boolean
    merchantTier: string
    jackpotCount: number
}

/**
 * 取得地圖標記（輕量端點，只回傳地圖必要欄位）
 */
export async function fetchMapMarkers(bounds?: string): Promise<MapMarkerData[]> {
    const { data } = await api.get('/api/retailers/map-markers', {
        params: bounds ? { bounds } : {},
    })
    return data
}

/* === 使用者 & Karma (Phase 2) === */

/** 使用者資料（LINE 登入） */
export interface UserData {
    id: number
    lineUserId: string
    displayName: string
    pictureUrl: string
    customNickname: string
    karmaPoints: number
    karmaLevel: number
    levelTitle: string
    levelWeight: number
    nextLevelPoints: number
    isBanned: number
}

/** Karma 紀錄 */
export interface KarmaLogData {
    id: number
    action: string
    points: number
    description: string
    retailerId: number | null
    createdAt: string
}

/** 庫存狀態 */
export interface InventoryItem {
    item: string
    status: string
    confidence: number
    updatedAt: string
}

/** 評分資料 */
export interface RatingData {
    id: number
    retailerId: number
    userId: number
    userName: string
    userLevel: number
    userPictureUrl: string
    rating: number
    serviceTags: string[]
    facilityTags: string[]
    comment: string
    isGpsVerified: boolean
    karmaWeight: number
    createdAt: string
}

/** 評分摘要 */
export interface RatingSummaryData {
    retailerId: number
    avgRating: number
    totalCount: number
    serviceTagStats: Record<string, number>
    facilityTagStats: Record<string, number>
}

/* === 認證 API (LINE Login) === */

/**
 * 設定 Authorization header
 * 讓後續需要登入的 API 自動帶入 Token
 */
export function setAuthToken(token: string | null) {
    if (token) {
        api.defaults.headers.common['Authorization'] = `Bearer ${token}`
    } else {
        delete api.defaults.headers.common['Authorization']
    }
}

/** LINE 登入（用授權碼換 Token） */
export async function loginWithLineCode(code: string): Promise<{ token: string; user: UserData }> {
    const { data } = await api.post('/api/auth/line', { code })
    return data
}

/** 取得當前登入使用者 */
export async function fetchAuthMe(): Promise<UserData> {
    const { data } = await api.get('/api/auth/me')
    return data
}

/** 更新暱稱 */
export async function updateProfile(customNickname: string): Promise<UserData> {
    const { data } = await api.put('/api/auth/profile', { customNickname })
    return data
}

/** 取得使用者資訊 */
export async function fetchUser(userId: number): Promise<UserData> {
    const { data } = await api.get(`/api/users/${userId}`)
    return data
}

/** 取得 Karma 紀錄 */
export async function fetchKarmaLogs(userId: number): Promise<KarmaLogData[]> {
    const { data } = await api.get(`/api/users/${userId}/karma-logs`)
    return data
}

/* === 評分 API === */

/** 新增評分 */
export async function submitRating(payload: {
    retailerId: number
    rating: number
    serviceTags: string[]
    facilityTags: string[]
    comment: string
    lat?: number
    lng?: number
}): Promise<RatingData> {
    const { data } = await api.post('/api/ratings', payload)
    return data
}

/** 取得店家評分列表 */
export async function fetchRetailerRatings(retailerId: number): Promise<RatingData[]> {
    const { data } = await api.get(`/api/ratings/${retailerId}`)
    return data
}

/** 取得店家評分摘要 */
export async function fetchRatingSummary(retailerId: number): Promise<RatingSummaryData> {
    const { data } = await api.get(`/api/ratings/${retailerId}/summary`)
    return data
}

/** 回報庫存 */
export async function reportInventory(payload: {
    retailerId: number
    userId: number
    item: string
    status: string
    lat?: number
    lng?: number
}): Promise<unknown> {
    const { data } = await api.post('/api/inventory/report', payload)
    return data
}

/** 取得某店庫存狀態 */
export async function fetchInventory(retailerId: number): Promise<{ retailerId: number; items: InventoryItem[] }> {
    const { data } = await api.get(`/api/inventory/${retailerId}`)
    return data
}

/** 商家官方庫存品項 */
export interface MerchantInventoryData {
    itemName: string
    itemPrice: number
    status: string
    scratchcardId?: number | null
    updatedAt: string | null
}

/** 取得某店商家官方庫存狀態 */
export async function fetchMerchantOfficialInventory(retailerId: number): Promise<{
    retailerId: number
    items: MerchantInventoryData[]
}> {
    const { data } = await api.get(`/api/inventory/${retailerId}/merchant`)
    return data
}

/** 附近有貨的店家資訊 */
export interface NearbyStockStore {
    retailerId: number
    retailerName: string
    address: string
    city: string
    district: string
    lat: number | null
    lng: number | null
    status: string
    updatedAt: string | null
    isClaimed: boolean
    merchantTier: string
    distance: number | null
}

/** 依刮刮樂 ID 查詢附近有存貨的店家 */
export async function fetchNearbyStock(scratchcardId: number, lat?: number, lng?: number): Promise<{
    scratchcardId: number
    stores: NearbyStockStore[]
}> {
    const params: Record<string, unknown> = {}
    if (lat !== undefined) params.lat = lat
    if (lng !== undefined) params.lng = lng
    const { data } = await api.get(`/api/inventory/scratchcard/${scratchcardId}/nearby`, { params })
    return data
}

/* === 店家管理 (Phase 3) === */

/** 認領回應 */
export interface MerchantClaimData {
    id: number
    retailerId: number
    userId: number
    status: string
    tier: string
    createdAt: string
}

/** 提交店家認領 */
export async function submitMerchantClaim(payload: {
    retailerId: number
    userId: number
    contactName?: string
    contactPhone?: string
    licenseUrl?: string
    idCardUrl?: string
}): Promise<MerchantClaimData> {
    const { data } = await api.post('/api/merchant/claim', payload)
    return data
}

/** 上傳圖片 */
export async function uploadImage(file: File): Promise<{ status: string; url: string }> {
    const formData = new FormData()
    formData.append('file', file)
    const { data } = await api.post('/api/upload', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    })
    return data
}

/** 更新店家設施標籤 */
export async function updateRetailerTags(retailerId: number, tags: Record<string, boolean>): Promise<unknown> {
    const { data } = await api.put(`/api/merchant/${retailerId}/tags`, tags)
    return data
}

/** 更新營業狀態 */
export async function updateBusinessStatus(retailerId: number, isActive: boolean): Promise<unknown> {
    const { data } = await api.put(`/api/merchant/${retailerId}/status`, null, { params: { is_active: isActive } })
    return data
}

/** 發佈臨時公告 */
export async function createAnnouncement(retailerId: number, content: string): Promise<unknown> {
    const { data } = await api.post(`/api/merchant/${retailerId}/announcement`, { content })
    return data
}

/* === 節慶模式 (Phase 4) === */

/** 節慶狀態 */
export interface FestivalStatus {
    isActive: boolean
    name: string
    description: string
    startDate: string | null
    endDate: string | null
}

/** 熱力圖資料點 */
export interface HeatmapPoint {
    city: string
    district: string
    lat: number
    lng: number
    jackpotCount: number
    retailerCount: number
}

/** 取得節慶模式狀態 */
export async function fetchFestivalStatus(): Promise<FestivalStatus> {
    const { data } = await api.get('/api/festival/status')
    return data
}

/** 取得熱力圖資料 */
export async function fetchHeatmap(minJackpot?: number): Promise<HeatmapPoint[]> {
    const { data } = await api.get('/api/festival/heatmap', {
        params: { min_jackpot: minJackpot },
    })
    return data
}

/** 公開搜尋刮刮樂款式（僅回傳未過期款式） */
export interface ScratchcardSearchItem {
    id: number
    gameId: string
    name: string
    price: number
    imageUrl: string
}

export async function searchScratchcardsPublic(q: string): Promise<ScratchcardSearchItem[]> {
    const { data } = await api.get('/api/inventory/scratchcards/search', { params: { q } })
    return data
}

/** 紀錄店家在地圖上被點擊查看次數 */
export async function recordRetailerClick(retailerId: number): Promise<void> {
    await api.post(`/api/map/retailer/${retailerId}/click`)
}

/** 紀錄店家在附近庫存被曝光次數 */
export async function recordRetailerExposure(retailerId: number): Promise<void> {
    await api.post(`/api/inventory/retailer/${retailerId}/exposure`)
}

/** 取得商家公開專屬頁面資料 (PRO) */
export async function fetchStorePage(retailerId: number) {
    const res = await api.get(`/api/store/${retailerId}`)
    return res.data
}
