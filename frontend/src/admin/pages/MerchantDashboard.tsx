/**
 * 商家 Dashboard 頁面
 * 顯示專屬該店家的數據
 */
import { useState, useEffect } from 'react'
import {
  Box,
  Typography,
  Card,
  CardContent,
  Grid,
  Skeleton,
  Chip,
} from '@mui/material'
import StorefrontIcon from '@mui/icons-material/Storefront'
import LocationIcon from '@mui/icons-material/LocationOn'
import WorkspacePremiumIcon from '@mui/icons-material/WorkspacePremium'
import { fetchMyStore, createPaymentOrder } from '../api'
import { useAdminAuth } from '../AdminAuthContext'
import { useSnackbar } from 'notistack'

interface StoreData {
  id: number
  name: string
  address: string
  city: string
  district: string
  lat: number | null
  lng: number | null
  isActive: boolean
  merchantTier: string
  tierExpireAt?: string | null
  announcement: string
  mapClickCount: number
  nearbyInventoryCount: number
  claimId?: number | null
}

export default function MerchantDashboard() {
  const [store, setStore] = useState<StoreData | null>(null)
  const [loading, setLoading] = useState(true)
  const [upgrading, setUpgrading] = useState(false)
  const { enqueueSnackbar } = useSnackbar()
  const { currentRetailerId } = useAdminAuth()

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const data = await fetchMyStore(currentRetailerId ?? undefined)
        setStore(data)
      } catch {
        // NOTE: 錯誤由 axios 攔截器統一處理
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [currentRetailerId])

  if (loading) {
    return (
      <Box>
        <Skeleton height={60} width={200} sx={{ mb: 3 }} />
        <Skeleton height={200} />
      </Box>
    )
  }

  if (!store) {
    return (
      <Box sx={{ textAlign: 'center', py: 8 }}>
        <Typography variant="h6" color="text.secondary">
          尚未關聯店家，請聯繫管理員設定
        </Typography>
      </Box>
    )
  }

  const handleUpgrade = async (plan: string, amount: number) => {
    try {
      setUpgrading(true)
      const res = await createPaymentOrder(store.id, plan, amount)
      if (res.status === 'success') {
        const { MerchantID, TradeInfo, TradeSha, Version, PaymentUrl } = res.data
        // 動態建立 Form 並送出至藍新金流
        const form = document.createElement('form')
        form.method = 'POST'
        form.action = PaymentUrl
        
        const args = { MerchantID, TradeInfo, TradeSha, Version }
        Object.entries(args).forEach(([key, value]) => {
          const input = document.createElement('input')
          input.type = 'hidden'
          input.name = key
          input.value = value
        })
        
        document.body.appendChild(form)
        form.submit()
      }
    } catch (err: any) {
      console.error(err)
      enqueueSnackbar('無法建立訂單，請稍後再試。', { variant: 'error' })
      setUpgrading(false) // form.submit 成功會跳轉離開所以不一定會觸發此區，但保險起見加在這裡
    }
  }

  return (
    <Box>
      <Typography variant="h5" fontWeight={700} mb={3}>
        店舖總覽
      </Typography>

      {/* 統計指標區塊 */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <Card sx={{ height: '100%', bgcolor: 'primary.main', color: 'primary.contrastText' }}>
            <CardContent>
              <Typography variant="subtitle2" sx={{ opacity: 0.8, mb: 1 }}>
                地圖總點擊次數 👀
              </Typography>
              <Typography variant="h3" fontWeight={700}>
                {store.mapClickCount || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
          <Card sx={{ height: '100%', bgcolor: 'secondary.main', color: 'secondary.contrastText' }}>
            <CardContent>
              <Typography variant="subtitle2" sx={{ opacity: 0.8, mb: 1 }}>
                附近有貨曝光次數 🎯
              </Typography>
              <Typography variant="h3" fontWeight={700}>
                {store.nearbyInventoryCount || 0}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
                <Box
                  sx={{
                    width: 48, height: 48, borderRadius: 2,
                    bgcolor: '#0B192C', display: 'flex',
                    alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  <StorefrontIcon sx={{ color: '#fff' }} />
                </Box>
                <Box>
                  <Typography variant="h6" fontWeight={700}>
                    {store.name}
                  </Typography>
                  <Chip
                    label={store.isActive ? '營業中' : '停業中'}
                    color={store.isActive ? 'success' : 'default'}
                    size="small"
                  />
                </Box>
              </Box>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, color: 'text.secondary' }}>
                <LocationIcon fontSize="small" />
                <Typography variant="body2">{store.address}</Typography>
              </Box>
              {store.merchantTier && (
                <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
                  <Chip
                    label={store.merchantTier === 'pro' ? '專業版' : '基礎版'}
                    color={store.merchantTier === 'pro' ? 'primary' : 'default'}
                    variant={store.merchantTier === 'pro' ? 'filled' : 'outlined'}
                    icon={store.merchantTier === 'pro' ? <WorkspacePremiumIcon /> : undefined}
                  />
                  {store.merchantTier === 'pro' && store.tierExpireAt && (
                    <Typography variant="body2" color="text.secondary">
                      到期日：{new Date(store.tierExpireAt).toLocaleDateString()}
                    </Typography>
                  )}
                </Box>
              )}
              {store.merchantTier !== 'pro' && (
                <Box sx={{ mt: 3, pt: 2, borderTop: '1px solid #eaeaea' }}>
                  <Typography variant="subtitle2" mb={1}>💎 升級 PRO 專業版</Typography>
                  <Typography variant="body2" color="text.secondary" mb={1}>享有專業商家頁面、中獎牆展示、數據分析、優先搜尋排名等進階功能。</Typography>
                  <Box sx={{ display: 'flex', gap: 2, mt: 2 }}>
                    <Chip
                      label="立即升級 PRO — NT$1,680/年"
                      sx={{
                        background: 'linear-gradient(135deg, #d4af37, #a855f7)',
                        color: '#fff', fontWeight: 600, fontSize: '0.9rem',
                        px: 2, py: 2.5, cursor: 'pointer',
                        '&:hover': { opacity: 0.9, transform: 'scale(1.02)' },
                      }}
                      onClick={async () => {
                        if (!store?.claimId) {
                          enqueueSnackbar('找不到認領資料，請聯繫管理員', { variant: 'error' })
                          return
                        }
                        try {
                          const { fetchCheckoutUrl } = await import('../api')
                          const data = await fetchCheckoutUrl(store.claimId!)
                          if (data.checkoutUrl) {
                            window.open(data.checkoutUrl, '_blank')
                          } else {
                            enqueueSnackbar('無法取得付款連結', { variant: 'error' })
                          }
                        } catch {
                          enqueueSnackbar('取得付款連結失敗', { variant: 'error' })
                        }
                      }}
                      clickable
                    />
                  </Box>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 6 }}>
          <Card sx={{ height: '100%' }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="subtitle1" fontWeight={600} mb={2}>
                目前公告
              </Typography>
              <Typography variant="body1" color={store.announcement ? 'text.primary' : 'text.secondary'}>
                {store.announcement || '尚未設定公告'}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  )
}
