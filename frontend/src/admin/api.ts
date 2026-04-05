/**
 * Admin 後台 API 服務層
 * 統一管理所有後台 API 呼叫
 */
import axios from 'axios'
import { toast } from '../utils/toast'

const API_BASE = import.meta.env.VITE_API_BASE
  ? `${import.meta.env.VITE_API_BASE}/api/admin`
  : 'http://localhost:8000/api/admin'
const ADMIN_TOKEN_KEY = 'admin_auth_token'

/** 建立帶有 Auth Header 的 axios 實例 */
const adminApi = axios.create({
  baseURL: API_BASE,
})

/** 請求攔截器：自動附加 Token */
adminApi.interceptors.request.use((config) => {
  const token = localStorage.getItem(ADMIN_TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

/** 回應攔截器：處理 401 自動登出及全域錯誤提示 */
adminApi.interceptors.response.use(
  (res) => res,
  (error) => {
    // 處理 401 登出
    if (error.response?.status === 401) {
      localStorage.removeItem(ADMIN_TOKEN_KEY)
      window.location.href = '/admin/login'
      toast.error('登入已逾期，請重新登入')
      return Promise.reject(error)
    }

    // 擷取後端回傳的錯誤細節
    const detail = error.response?.data?.detail
    const message = typeof detail === 'string' ? detail : detail?.[0]?.msg || error.message || '發生未知錯誤'
    toast.error(message)

    return Promise.reject(error)
  }
)

// ─── 型別定義 ───────────────────────────────────────

export interface AdminUser {
  id: number
  username: string
  displayName: string
  role: 'SUPER_ADMIN' | 'ADMIN' | 'MERCHANT'
  retailerId: number | null
  isActive: number
  expireAt: string | null
  lastLoginAt: string | null
  createdAt: string | null
}

export interface DashboardStats {
  totalRetailers: number
  activeRetailers: number
  twLotteryCount: number
  sportsLotteryCount: number
  totalScratchcards: number
  totalUsers: number
  totalReports: number
  claimedRetailers: number
}

export interface TrafficAnalytics {
  daily: { date: string; visits: number; pageviews: number }[]
  topPages: { path: string; views: number }[]
  topCountries: { country: string; views: number }[]
  topReferrers: { host: string; views: number }[]
}

export interface RetailerItem {
  id: number
  name: string
  address: string
  city: string
  district: string
  source: string
  lat: number | null
  lng: number | null
  isActive: boolean
  isClaimed: boolean
  merchantTier: string
  manualRating?: number | null
  jackpotCount?: number | null
}

export interface ScratchcardItem {
  id: number
  gameId: string
  name: string
  price: number
  maxPrize: string
  totalIssued: number
  salesRate: string
  grandPrizeCount: number
  grandPrizeUnclaimed: number
  overallWinRate: string
  imageUrl: string
}

// ─── 認證 API ───────────────────────────────────────

/** 管理員登入 */
export async function adminLogin(username: string, password: string) {
  const res = await adminApi.post('/auth/login', { username, password })
  const { token, user } = res.data
  localStorage.setItem(ADMIN_TOKEN_KEY, token)
  return user as AdminUser
}

/** 取得當前管理員資料 */
export async function fetchAdminMe(): Promise<AdminUser> {
  const res = await adminApi.get('/auth/me')
  return res.data
}

/** 管理員登出 */
export function adminLogout() {
  localStorage.removeItem(ADMIN_TOKEN_KEY)
}

/** 檢查是否已登入 */
export function isAdminLoggedIn(): boolean {
  return !!localStorage.getItem(ADMIN_TOKEN_KEY)
}

// ─── 帳號管理 API ───────────────────────────────────

/** 列出所有管理員帳號 */
export async function fetchAdminUsers(): Promise<AdminUser[]> {
  const res = await adminApi.get('/users')
  return res.data
}

/** 建立管理員帳號 */
export async function createAdminUser(data: {
  username: string
  password: string
  displayName: string
  role: string
  retailerId?: number | null
  expireAt?: string | null
}): Promise<AdminUser> {
  const res = await adminApi.post('/users', data)
  return res.data
}

/** 刪除管理員帳號 */
export async function deleteAdminUser(userId: number): Promise<void> {
  await adminApi.delete(`/users/${userId}`)
}

/** 重設管理員密碼（超級管理員用） */
export async function resetAdminPassword(userId: number): Promise<{ message: string }> {
  const res = await adminApi.post(`/users/${userId}/reset-password`)
  return res.data
}

/** 更新管理員帳號（角色、retailerId 等） */
export async function updateAdminUser(userId: number, data: {
  displayName?: string
  role?: string
  retailerId?: number | null
  isActive?: boolean
  expireAt?: string | null
  proExpiresAt?: string | null
}): Promise<AdminUser> {
  const res = await adminApi.put(`/users/${userId}`, data)
  return res.data
}

/** 修改密碼 */
export async function changeAdminPassword(oldPassword: string, newPassword: string): Promise<void> {
  await adminApi.post('/users/change-password', { oldPassword, newPassword })
}

// ─── Dashboard API ──────────────────────────────────

/** 取得營運統計 */
export async function fetchDashboardStats(): Promise<DashboardStats> {
  const res = await adminApi.get('/dashboard/stats')
  return res.data
}

/** 取得流量統計 (Cloudflare) */
export async function fetchTrafficAnalytics(): Promise<TrafficAnalytics> {
  const res = await adminApi.get('/dashboard/traffic')
  return res.data
}

/** 手動觸發頭獎店家同步爬蟲 */
export async function triggerJackpotSync(): Promise<{message: string}> {
  const res = await adminApi.post('/trigger-jackpot-sync')
  return res.data
}

// ─── 彩券行管理 API ─────────────────────────────────

/** 列出彩券行 */
export async function fetchRetailers(params: {
  page?: number
  pageSize?: number
  search?: string
  city?: string
  district?: string
}) {
  const res = await adminApi.get('/retailers', { params })
  return res.data as { total: number; page: number; pageSize: number; items: RetailerItem[] }
}

/** 更新彩券行 */
export async function updateRetailer(id: number, data: Partial<RetailerItem>): Promise<void> {
  await adminApi.put(`/retailers/${id}`, data)
}

/** 搜尋彩券行 (供關聯使用) */
export async function searchRetailers(q: string): Promise<{id: number; name: string; address: string}[]> {
  const res = await adminApi.get('/retailers/search', { params: { q } })
  return res.data
}

/** 批量更新彩券行狀態 */
export async function bulkUpdateRetailerStatus(retailerIds: number[], isActive: boolean): Promise<void> {
  await adminApi.put('/retailers/bulk-status', { retailerIds, isActive })
}

// ─── 刮刮樂 API ─────────────────────────────────────

/** 列出刮刮樂商品 */
export async function fetchScratchcards(params: { page?: number; pageSize?: number; showExpired?: boolean }) {
  const res = await adminApi.get('/scratchcards', { params })
  return res.data as { total: number; page: number; pageSize: number; items: ScratchcardItem[] }
}

// ─── 商家專屬 API ───────────────────────────────────

/** 取得商家自己的店舖 */
export async function fetchMyStore() {
  const res = await adminApi.get('/merchant/my-store')
  return res.data
}

/** 更新商家自己的店舖 */
export async function updateMyStore(data: Record<string, unknown>): Promise<void> {
  await adminApi.put('/merchant/my-store', data)
}

/** 取得 PRO 升級結帳連結 */
export async function fetchCheckoutUrl(claimId: number) {
  const res = await adminApi.get(`/merchant/claim/${claimId}/checkout-url`)
  return res.data
}

/** 建立升級訂單（取得金流參數） */
export async function createPaymentOrder(retailerId: number, plan: string, amount: number) {
  const res = await adminApi.post('/payment/create', { retailer_id: retailerId, plan, amount })
  return res.data
}

// ─── 商家庫存管理 API ───────────────────────────────

/** 庫存品項 */
export interface MerchantInventoryItem {
  id?: number
  itemName: string
  itemPrice: number
  status: string
  scratchcardId?: number | null
  gameId?: string
  imageUrl?: string
  redeemDeadline?: string
  updatedAt?: string | null
}

/** 可選刮刮樂（搜尋結果） */
export interface ScratchcardOption {
  id: number
  gameId: string
  name: string
  price: number
  imageUrl: string
  redeemDeadline: string
}

/** 搜尋可用的刮刮樂款式（排除過期） */
export async function searchScratchcards(q: string): Promise<ScratchcardOption[]> {
  const res = await adminApi.get('/merchant/scratchcards/search', { params: { q } })
  return res.data
}

/** 取得商家庫存清單 */
export async function fetchMerchantInventory(): Promise<MerchantInventoryItem[]> {
  const res = await adminApi.get('/merchant/inventory')
  return res.data
}

/** 批量更新庫存狀態 */
export async function updateMerchantInventory(items: MerchantInventoryItem[]): Promise<void> {
  await adminApi.put('/merchant/inventory', items)
}

/** 刪除庫存品項 */
export async function deleteMerchantInventoryItem(itemId: number): Promise<void> {
  await adminApi.delete(`/merchant/inventory/${itemId}`)
}

/** 取得商家自己的照片（後台專用，僅 PRO） */
export async function fetchMerchantPhotos(): Promise<{ gallery: any[]; winningWall: any[] }> {
  const res = await adminApi.get('/merchant/photos')
  return res.data
}

// ─── 社群使用者管理 API ───────────────────────────────────

export interface CommunityUserItem {
  id: number
  lineUserId: string
  displayName: string
  customNickname: string
  pictureUrl: string
  karmaPoints: number
  karmaLevel: number
  levelTitle: string
  levelWeight: number
  isBanned: boolean
  createdAt: string | null
}

export interface CommunityUserHistory {
  user: CommunityUserItem
  karmaLogs: any[]
  inventoryReports: any[]
  ratings: any[]
}

/** 取得社群使用者清單 */
export async function fetchCommunityUsers(params: { page?: number; pageSize?: number; search?: string }) {
  const res = await adminApi.get('/community-users', { params })
  return res.data as { total: number; page: number; pageSize: number; items: CommunityUserItem[], levels: Record<string, any> }
}

/** 取得社群使用者歷史紀錄 */
export async function fetchCommunityUserHistory(userId: number) {
  const res = await adminApi.get(`/community-users/${userId}/history`)
  return res.data as CommunityUserHistory
}

/** 調整社群使用者積分 */
export async function adjustCommunityUserKarma(userId: number, data: { points?: number; reason?: string; set_to?: number | null }) {
  const res = await adminApi.put(`/community-users/${userId}/karma`, data)
  return res.data
}

/** 批量封禁/解封社群使用者 */
export async function bulkBanCommunityUsers(userIds: number[], isBanned: boolean): Promise<void> {
  await adminApi.put('/community-users/bulk-ban', { userIds, isBanned })
}

// ─── 認領管理 API (純後台介面呼叫 /api/merchant) ────────────

export interface MerchantClaimItem {
  id: number
  retailerId: number
  storeName: string
  userId: number
  lineDisplayName: string
  contactName: string
  contactPhone: string
  licenseUrl: string
  idCardUrl: string
  status: 'pending' | 'approved' | 'rejected'
  tier: string
  rejectReason: string
  createdAt: string
  approvedAt: string | null
}

/** 取得所有店家認領申請 */
export async function fetchMerchantClaims(status?: string): Promise<MerchantClaimItem[]> {
  const res = await adminApi.get('/merchant-claims', {
    params: { status }
  })
  return res.data
}

/** 核准店家認領 */
export async function approveMerchantClaim(claimId: number): Promise<void> {
  await adminApi.put(`/merchant-claims/${claimId}/approve`)
}

/** 駁回店家認領 */
export async function rejectMerchantClaim(claimId: number, reason: string): Promise<void> {
  await adminApi.put(`/merchant-claims/${claimId}/reject`, null, {
    params: { reason }
  })
}

export default adminApi

// ─── 商家專屬頁面管理 API ────────────────────────────────

/** 更新商家專屬頁面文字資訊 */
export async function updateStorePage(data: Record<string, unknown>): Promise<void> {
    await adminApi.put('/merchant/store-page', data)
}

/** 上傳商家圖片（相簿或中獎牆） */
export async function uploadStorePhoto(file: File, category: string, caption: string) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('category', category)
    formData.append('caption', caption)
    const res = await adminApi.post('/merchant/photos', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
}

/** 刪除商家圖片 */
export async function deleteStorePhoto(photoId: number): Promise<void> {
    await adminApi.delete(`/merchant/photos/${photoId}`)
}

/** 上傳商家 Banner */
export async function uploadStoreBanner(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    const res = await adminApi.post('/merchant/banner', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data as { bannerUrl: string }
}
