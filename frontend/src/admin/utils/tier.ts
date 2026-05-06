/**
 * 商家方案狀態判斷
 * 同時檢查 tier 與到期日，避免「tier=pro 但已過期」的殘留狀態誤放權限
 */
import type { MerchantStore } from '../api'

export function isStorePro(store: MerchantStore | undefined | null): boolean {
  if (!store) return false
  if (store.merchantTier !== 'pro') return false
  // 永久 PRO (9999-12-31) 或無到期日 -> 視為有效
  if (!store.tierExpireAt) return true
  const expire = new Date(store.tierExpireAt).getTime()
  if (Number.isNaN(expire)) return true  // 解析失敗時保守視為有效，避免誤鎖
  return expire > Date.now()
}
